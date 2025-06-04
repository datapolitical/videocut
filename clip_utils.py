#!/usr/bin/env python3
"""clip_utils.py – identify, cut, and stitch video clips

Updated 1 Jun 2025
• Added automatic speaker‑mapping helpers (Nicholson).
• Completed concatenate_clips implementation with correct stream count.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

# ───────────────────────── Constants ─────────────────────────
WHITE_FLASH_SEC = 0.5
FADE_SEC        = 0.5
TARGET_W, TARGET_H = 1280, 720
TARGET_FPS      = 30

# ────────────────────────── JSON → TSV ───────────────────────

def json_to_tsv(json_path: str, out_tsv: str = "input.tsv") -> None:
    """Convert WhisperX JSON into a TSV for spreadsheet editing.

    The TSV will contain ``start``, ``end``, ``speaker`` and ``text`` columns
    with an empty ``keep`` column ready for marking clips to retain.
    """
    data = json.loads(Path(json_path).read_text())
    segs = data.get("segments", data)

    with open(out_tsv, "w", newline="") as f:
        wr = csv.writer(f, delimiter="\t")
        wr.writerow(["start", "end", "speaker", "text", "keep"])
        for seg in segs:
            wr.writerow([
                seg.get("start"),
                seg.get("end"),
                seg.get("speaker", ""),
                str(seg.get("text", "")).replace("\n", " "),
                "",
            ])

    print(f"✅  {len(segs)} segment(s) → {out_tsv}")

# ────────────────────── JSON → editable JSON ──────────────────────

def json_to_editable(json_path: str, out_json: str = "segments_edit.json") -> None:
    """Create an editable JSON with a ``keep`` flag and context fields.

    The output format mirrors ``auto_segment_nicholson.py`` so each entry
    contains ``Timestamp`` ("start–end"), ``content`` (segment text), empty
    ``pre``/``post`` placeholders and an integer ``id`` for reference.
    """
    data = json.loads(Path(json_path).read_text())
    segs_in = data.get("segments", data)

    segs: List[Dict] = []
    for i, seg in enumerate(segs_in, 1):
        segs.append({
            "id": i,
            "start": seg.get("start"),
            "end": seg.get("end"),
            "Timestamp": f"[{seg.get('start')}-{seg.get('end')}]",
            "content": str(seg.get("text", "")).strip(),
            "speaker": seg.get("speaker", ""),
            "pre": [],
            "post": [],
            "keep": False,
        })

    Path(out_json).write_text(json.dumps(segs, indent=2))
    print(f"✅  {len(segs)} segment(s) → {out_json}")

# ────────────────────────── TSV → JSON ───────────────────────

def identify_clips(tsv: str = "input.tsv", out_json: str = "segments_to_keep.json") -> None:
    """Save rows marked *keep* in **input.tsv** as JSON segments."""
    if not Path(tsv).exists():
        sys.exit(f"❌  {tsv} not found")

    segs: List[Dict[str, float]] = []
    with open(tsv, newline="") as f:
        rdr = csv.DictReader(f, delimiter="\t")
        for row in rdr:
            if str(row.get("keep", "")).strip().lower() not in {"1", "true", "yes", "✔"}:
                continue
            segs.append({"start": float(row["start"]), "end": float(row["end"])})

    Path(out_json).write_text(json.dumps(segs, indent=2))
    print(f"✅  {len(segs)} clip(s) flagged → {out_json}")

# ─────────────────────── editable JSON → JSON ───────────────────────

def identify_clips_json(edit_json: str = "segments_edit.json", out_json: str = "segments_to_keep.json") -> None:
    """Save segments with ``keep`` true in *edit_json* to a simple JSON list."""
    if not Path(edit_json).exists():
        sys.exit(f"❌  {edit_json} not found")

    raw = json.loads(Path(edit_json).read_text())
    segs_in = raw if isinstance(raw, list) else raw.get("segments", raw)

    segs: List[Dict[str, float]] = []
    for seg in segs_in:
        keep = str(seg.get("keep", "")).strip().lower()
        if keep not in {"1", "true", "yes", "✔", "x"}:
            continue
        segs.append({"start": float(seg["start"]), "end": float(seg["end"] )})

    Path(out_json).write_text(json.dumps(segs, indent=2))
    print(f"✅  {len(segs)} clip(s) flagged → {out_json}")

# ─────────────── markup_guide → JSON (manual) ───────────────

def extract_marked(markup: str = "markup_guide.txt", out_json: str = "segments_to_keep.json") -> None:
    """Parse **markup_guide.txt** and dump JSON segment list."""
    if not Path(markup).exists():
        sys.exit("❌  markup_guide.txt not found – run transcription first")

    segs, open_start = [], None
    for ln, line in enumerate(Path(markup).read_text().splitlines(), 1):
        line = line.strip()
        if line.startswith("[") and "–" in line:
            ts = line.split("]")[0][1:].replace("–", "-")
            try:
                s, e = map(float, ts.split("-"))
                segs.append({"start": s, "end": e})
            except ValueError:
                print(f"⚠️  bad timestamp line {ln}")
        elif line.startswith("START ["):
            open_start = float(line[line.find("[")+1:line.find("-")])
        elif line.startswith("END [") and open_start is not None:
            end = float(line[line.find("-")+1:line.find("]")])
            segs.append({"start": open_start, "end": end})
            open_start = None

    Path(out_json).write_text(json.dumps(segs, indent=2))
    print(f"✅  {len(segs)} segment(s) → {out_json}")

# ─────────────── Auto‑mapping Secretary Nicholson ───────────────

_NICHOLSON_KEY_PHRASES = {
    "secretary nicholson",
    "director nicholson",
    "nicholson, for the record",
}

def map_nicholson_speaker(diarized_json: str) -> str:
    """Return the WhisperX speaker label that matches Nicholson."""
    data = json.loads(Path(diarized_json).read_text())
    counts: Dict[str, int] = {}
    for seg in data["segments"]:
        spk = seg.get("speaker")
        if not spk:
            continue
        text_l = seg["text"].lower()
        if any(p in text_l for p in _NICHOLSON_KEY_PHRASES):
            counts[spk] = counts.get(spk, 0) + 1

    if not counts:
        raise RuntimeError("Nicholson phrases not found – update key phrases or re‑check diarization.")

    best = max(counts, key=counts.get)
    print(f"🔍  Identified Secretary Nicholson as {best} (matches={counts[best]})")
    return best

def auto_segments_for_speaker(diarized_json: str, speaker_id: str, out_json: str = "segments_to_keep.json") -> None:
    """Dump every segment spoken by *speaker_id* into JSON."""
    data = json.loads(Path(diarized_json).read_text())
    segs = [{"start": seg["start"], "end": seg["end"]}
            for seg in data["segments"] if seg.get("speaker") == speaker_id]
    Path(out_json).write_text(json.dumps(segs, indent=2))
    print(f"✅  {len(segs)} Nicholson segment(s) → {out_json}")

def auto_mark_nicholson(diarized_json: str, out_json: str = "segments_to_keep.json") -> None:
    """End‑to‑end helper to create JSON for Nicholson’s clips."""
    spk = map_nicholson_speaker(diarized_json)
    auto_segments_for_speaker(diarized_json, spk, out_json)

# ───────── helper: fade & pad re‑encode ─────────

def _build_faded_clip(src: Path, dst: Path) -> None:
    dur = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "format=duration", "-of", "csv=p=0", str(src)
    ], text=True).strip())
    end_time = max(dur - FADE_SEC, 0)

    vf = (
        f"fps={TARGET_FPS},scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"  # noqa: E231
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:color=white,"  # noqa: E231
        f"format=yuv420p,fade=t=in:st=0:d={FADE_SEC},fade=t=out:st={end_time}:d={FADE_SEC}"
    )
    af = f"afade=t=in:st=0:d={FADE_SEC},afade=t=out:st={end_time}:d={FADE_SEC}"

    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(src),
        "-vf", vf, "-af", af,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k", str(dst)
    ], check=True)

# ───────────────────────── generate_clips ───────────────────────

def generate_clips(input_video: str, seg_json: str = "segments_to_keep.json", out_dir: str = "clips") -> None:
    if not Path(seg_json).exists():
        sys.exit("❌  segments_to_keep.json missing – run clip identification")
    segs = json.loads(Path(seg_json).read_text())
    Path(out_dir).mkdir(exist_ok=True)
    for i, seg in enumerate(segs):
        tmp  = Path(out_dir) / f"tmp_{i:03d}.mp4"
        final = Path(out_dir) / f"clip_{i:03d}.mp4"
        print(f"🎬  clip_{i:03d}  {seg['start']:.2f}–{seg['end']:.2f}")
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-ss", str(seg['start']), "-to", str(seg['end']),
            "-i", input_video, "-c", "copy", str(tmp)
        ], check=True)
        _build_faded_clip(tmp, final)
        tmp.unlink()
    print(f"✅  {len(segs)} polished clip(s) in {out_dir}/")

# ───────────────────── concatenate_clips ────────────────────────

def concatenate_clips(clips_dir: str = "clips", out_file: str = "final_video.mp4") -> None:
    clips = sorted(Path(clips_dir).glob("clip_*.mp4"))
    if not clips:
        sys.exit("❌  No clips found – run generate_clips first")

    w, h = map(str, subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
        "-of", "csv=p=0", str(clips[0])
    ], text=True).strip().split(','))

    inputs: List[str] = []
    for idx, c in enumerate(clips):
        inputs += ["-i", str(c)]
        if idx < len(clips) - 1:
            inputs += ["-f", "lavfi", "-i", f"color=white:s={w}x{h}:d={WHITE_FLASH_SEC}"]

    # Count actual input streams by counting "-i"
    v_n = inputs.count("-i")
    a_n = len(clips)

    v_filter = f"concat=n={v_n}:v=1:a=0[v]"
    a_filter = f"concat=n={a_n}:v=0:a=1[a]"

    subprocess.run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", v_filter + ";" + a_filter,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k", out_file
    ], check=True)
    print(f"🏁  {out_file} assembled ({len(clips)} clips + white flashes)")

__all__ = [
    "json_to_tsv", "json_to_editable", "identify_clips", "identify_clips_json", "extract_marked",
    "map_nicholson_speaker", "auto_segments_for_speaker", "auto_mark_nicholson",
    "generate_clips", "concatenate_clips",
]

#!/usr/bin/env python3
"""process_video.py – merged, with full feature set (June 1 2025)

End‑to‑end pipeline:
  1. WhisperX transcription  (optional diarization)
  2. TSV or markup‑guide → JSON clip list
  3. Clip extraction  (frame‑accurate, with fade‑in/out & auto‑padding)
  4. Concatenation with white‑flash transitions

CLI flags:
  --transcribe            WhisperX on --input
  --diarize               add speaker diarization (needs --hf_token or HF_TOKEN)
  --identify-clips        read input.tsv → segments_to_keep.json
  --extract-marked        read markup_guide.txt → segments_to_keep.json
  --generate-clips        cut + polish clips to clips/clip_###.mp4
  --concatenate           stitch clips → final_video.mp4
"""

import argparse
import csv
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ───────────────────────────────────────── CONSTANTS ──────────────────────────
WHITE_FLASH_SEC   = 0.5   # bumper between clips
FADE_SEC          = 0.5   # per‑clip fade‑in/out
TARGET_W, TARGET_H = 1280, 720
TARGET_FPS        = 30

# ───────────────────────────────────────── HELPERS ────────────────────────────

def is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() in {"arm64", "arm"}

# ───────────────────────────────────── TRANSCRIPTION ──────────────────────────

def transcribe(input_video: str, hf_token: str | None, use_diarization: bool):
    """Run WhisperX and write markup_guide.txt."""

    compute_type = "float32" if is_apple_silicon() else "float16"
    out_json = f"{Path(input_video).stem}.json"

    cmd = ["whisperx", input_video, "--compute_type", compute_type, "--output_dir", "."]
    if use_diarization:
        if not hf_token:
            sys.exit("❌  --diarize needs --hf_token or HF_TOKEN env var")
        cmd += ["--diarize", "--hf_token", hf_token]

    print("🧠  WhisperX …")
    subprocess.run(cmd, check=True)
    if not Path(out_json).exists():
        sys.exit(f"❌  Expected {out_json} not found (WhisperX error)")

    data = json.loads(Path(out_json).read_text())
    with open("markup_guide.txt", "w") as g:
        for seg in data["segments"]:
            s, e = round(seg["start"], 2), round(seg["end"], 2)
            spk = seg.get("speaker", "SPEAKER") if use_diarization else "SPEAKER"
            txt = seg["text"].strip().replace("\n", " ")
            g.write(f"[{s}–{e}] {spk}: {txt}\n")
    print("✅  markup_guide.txt ready – mark your segments and/or edit input.tsv")

# ───────────────────────────── TSV → JSON IDENTIFY CLIPS ──────────────────────

def identify_clips(tsv="input.tsv", out_json="segments_to_keep.json"):
    """Convert an Excel‑edited TSV into a JSON list for clipping.

    TSV columns expected: start    end    keep    slug(optional)
    Only rows with truthy *keep* are output.
    """
    if not Path(tsv).exists():
        sys.exit(f"❌  '{tsv}' not found")

    segs = []
    with open(tsv, newline="") as f:
        rdr = csv.DictReader(f, delimiter="\t")
        for row in rdr:
            if str(row.get("keep", "")).strip() in {"", "0", "false", "False"}:
                continue
            segs.append({
                "start": float(row["start"]),
                "end"  : float(row["end"]),
                "slug" : row.get("slug") or f"clip_{len(segs):03d}"
            })
    Path(out_json).write_text(json.dumps(segs, indent=2))
    print(f"✅  {len(segs)} clip(s) flagged → {out_json}")

# ───────────────────────────── MARKUP → JSON EXTRACT ─────────────────────────

def extract_marked(markup="markup_guide.txt", out_json="segments_to_keep.json"):
    if not Path(markup).exists():
        sys.exit(f"❌  '{markup}' not found – run --transcribe first")

    segs, open_start = [], None
    for ln, line in enumerate(Path(markup).read_text().splitlines(), 1):
        line = line.strip()
        if line.startswith("[") and "–" in line:
            ts = line.split("]")[0][1:].replace("–", "-")
            try:
                s, e = map(float, ts.split("-"))
                segs.append({"start": s, "end": e})
            except ValueError:
                print(f"⚠️  bad timestamp on line {ln}")
        elif line.startswith("START ["):
            open_start = float(line[line.find("[")+1:line.find("-")])
        elif line.startswith("END [") and open_start is not None:
            end = float(line[line.find("-")+1:line.find("]")])
            segs.append({"start": open_start, "end": end})
            open_start = None
    Path(out_json).write_text(json.dumps(segs, indent=2))
    print(f"✅  {len(segs)} segment(s) → {out_json}")

# ──────────────────────────── BUILD FADED / PADDED CLIP ──────────────────────

def _build_faded_clip(src: Path, dst: Path):
    """Re‑encode *src* with fade‑in/out, scaling, padding, AAC/H.264."""
    # Probe duration
    dur = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "format=duration", "-of", "default=nw=1:nk=1", str(src)
    ]).strip())

    end_time = max(dur - FADE_SEC, 0)

    vf = (
        f"fps={TARGET_FPS},scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease," \
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:color=white," \
        f"format=yuv420p,fade=t=in:st=0:d={FADE_SEC},fade=t=out:st={end_time}:d={FADE_SEC}"
    )
    af = (
        f"afade=t=in:st=0:d={FADE_SEC},afade=t=out:st={end_time}:d={FADE_SEC}"
    )

    subprocess.run([
        "ffmpeg", "-y", "-i", str(src),
        "-vf", vf, "-af", af,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k", str(dst)
    ], check=True)

# ─────────────────────────────────── CLIP CUTTER ─────────────────────────────

def generate_clips(input_video: str, segments_json: str = "segments_to_keep.json", out_dir: str = "clips"):
    if not Path(segments_json).exists():
        sys.exit("❌  JSON of segments missing – run --identify-clips or --extract-marked")

    segs = json.loads(Path(segments_json).read_text())
    Path(out_dir).mkdir(exist_ok=True)

    for idx, seg in enumerate(segs):
        tmp  = Path(out_dir) / f"tmp_{idx:03d}.mp4"
        final = Path(out_dir) / f"clip_{idx:03d}.mp4"
        print(f"🎬  {final.name}  {seg['start']:.2f}–{seg['end']:.2f}")

        # Fast trim (key‑frame) then precise re‑encode with fades/pad
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-ss", str(seg["start"]), "-to", str(seg["end"]),
            "-i", input_video, "-c", "copy", str(tmp)
        ], check=True)
        _build_faded_clip(tmp, final)
        tmp.unlink()  # remove temp stream‑copy file

    print(f"✅  {len(segs)} polished clip(s) → {out_dir}/")

# ───────────────────────────────── CONCATENATION ─────────────────────────────

def concatenate_clips(clips_dir="clips", out_file="final_video.mp4"):
    clips = sorted(Path(clips_dir).glob("clip_*.mp4"))
    if not clips:
        sys.exit("❌  No clips – run --generate-clips first")

    # Probe geometry
    w, h = map(str, subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
        "-of", "csv=p=0", str(clips[0])
    ], text=True).strip().split(','))

    inputs = []
    for c in clips:
        inputs += ["-i", str(c)]
        if c != clips[-1]:
            inputs += ["-f", "lavfi", "-i", f"color=white:s={w}x{h}:d={WHITE_FLASH_SEC}"]

    v_count = len(inputs) // 2  # each "-i" counts one
    a_count = len(clips)

    filter_v = f"concat=n={v_count}:v=1:a=0[v]"
    filter_a = f"concat=n={a_count}:v=0:a=1[a]"

    subprocess.run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_v + ";" + filter_a,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", out_file
    ], check=True)
    print(f"🏁  {out_file} assembled ({len(clips)} clips + white flashes)")

# ───────────────────────────────────────── CLI ────────────────────────────────

def main():
    p = argparse.ArgumentParser("process_video")
    p.add_argument("--input", default="input.mp4", help="Input video")
    p.add_argument("--hf_token", default=os.getenv("HF_TOKEN"))
    p.add_argument("--transcribe", action="

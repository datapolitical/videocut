"""Transcript segmentation utilities."""
from __future__ import annotations
import csv
import json
import sys
import re
from pathlib import Path
from typing import Dict, List


def json_to_tsv(json_path: str, out_tsv: str = "input.tsv") -> None:
    """Convert WhisperX JSON to TSV for spreadsheet editing."""
    data = json.loads(Path(json_path).read_text())
    segs = data if isinstance(data, list) else data.get("segments", data)
    with open(out_tsv, "w", newline="") as f:
        wr = csv.writer(f, delimiter="\t")
        wr.writerow(["start", "end", "speaker", "text", "keep"])
        for seg in segs:
            wr.writerow([
                seg.get("start"),
                seg.get("end"),
                seg.get("label") or seg.get("speaker", ""),
                str(seg.get("text", "")).replace("\n", " "),
                "",
            ])
    print(f"✅  {len(segs)} segment(s) → {out_tsv}")


def json_to_markup(json_path: str, out_txt: str = "markup_guide.txt") -> None:
    """Write ``out_txt`` with ``[start-end] SPEAKER: text`` lines from *json_path*."""
    if not Path(json_path).exists():
        sys.exit(f"❌  {json_path} not found")

    data = json.loads(Path(json_path).read_text())
    segs = data if isinstance(data, list) else data.get("segments", data)
    lines = []
    for seg in segs:
        start = round(float(seg.get("start", 0)), 2)
        end = round(float(seg.get("end", 0)), 2)
        speaker = seg.get("label") or seg.get("speaker", "SPEAKER")
        text = str(seg.get("text", "")).replace("\n", " ").strip()
        lines.append(f"[{start}-{end}] {speaker}: {text}")

    Path(out_txt).write_text("\n".join(lines))
    print(f"✅  wrote {out_txt}")


_TS_RE = re.compile(r"^\s*\[(?P<start>\d+\.?\d*)[–-](?P<end>\d+\.?\d*)\]\s*(?P<rest>.*)")
PRE_SEC = 5
TRAIL_SEC = 30


def _load_markup(path: Path) -> List[dict]:
    lines = []
    if not path.exists():
        return lines
    for line in path.read_text().splitlines():
        m = _TS_RE.match(line)
        if not m:
            continue
        lines.append({"start": float(m.group("start")), "end": float(m.group("end")), "line": line})
    return lines


def _collect_pre(lines: List[dict], start: float) -> List[str]:
    window = start - PRE_SEC
    return [l["line"] for l in lines if l["end"] <= start and l["end"] >= window]


def _collect_post(lines: List[dict], end: float, next_start: float | None = None) -> List[str]:
    window = end + TRAIL_SEC
    out = []
    for l in lines:
        if l["start"] < end:
            continue
        if next_start is not None and l["start"] >= next_start:
            break
        if l["start"] > window:
            break
        out.append(l["line"])
    return out


def json_to_editable(json_path: str, out_json: str = "segments_edit.json", markup: str = "markup_guide.txt") -> None:
    """Create an editable JSON with keep flag and context lines."""
    data = json.loads(Path(json_path).read_text())
    segs_in = data if isinstance(data, list) else data.get("segments", data)
    markup_lines = _load_markup(Path(markup))
    segs: List[Dict] = []
    for i, seg in enumerate(segs_in, 1):
        start = float(seg.get("start"))
        end = float(seg.get("end"))
        next_start = float(segs_in[i]["start"]) if i < len(segs_in) else None
        if markup_lines:
            content_lines = [l["line"] for l in markup_lines if l["start"] < end and l["end"] > start]
            pre_lines = _collect_pre(markup_lines, start)
            post_lines = _collect_post(markup_lines, end, next_start)
            speaker = ""
            if content_lines:
                m = re.search(r"]\s*(\S+?):", content_lines[0])
                if m:
                    speaker = m.group(1)
            content = "\n".join(content_lines).strip()
        else:
            content = str(seg.get("text", "")).strip()
            speaker = seg.get("label") or seg.get("speaker", "")
            pre_lines = []
            post_lines = []

        segs.append({
            "id": i,
            "start": start,
            "end": end,
            "Timestamp": f"[{start}-{end}]",
            "content": content,
            "speaker": speaker,
            "pre": pre_lines,
            "post": post_lines,
            "keep": False,
        })

    Path(out_json).write_text(json.dumps(segs, indent=2))
    print(f"✅  {len(segs)} segment(s) → {out_json}")


def write_segments_txt_from_editable(editable_json: str, out_txt: str = "segments.txt"):
    """Write a full transcript with tabbed lines and =START=/=END= around keep=True segments."""
    data = json.loads(Path(editable_json).read_text())
    output = []
    in_segment = False

    for seg in data:
        lines = (seg.get("pre", []) + seg.get("lines", []) + seg.get("post", []))
        if seg.get("keep") and not in_segment:
            output.append("=START=")
            in_segment = True

        for line in lines:
            output.append(f"\t{line.strip()}")

        if not seg.get("keep") and in_segment:
            output.append("=END=")
            in_segment = False

    if in_segment:
        output.append("=END=")

    Path(out_txt).write_text("\n".join(output))
    print(f"✅ wrote {out_txt} with {output.count('=START=')} marked segments")


def identify_clips(tsv: str = "input.tsv", out_json: str = "segments_to_keep.json") -> None:
    """Save rows marked keep in TSV as JSON segments."""
    if not Path(tsv).exists():
        sys.exit(f"❌  {tsv} not found")
    segs: List[Dict[str, float]] = []
    with open(tsv, newline="") as f:
        rdr = csv.DictReader(f, delimiter="\t")
        for row in rdr:
            if str(row.get("keep", "")).strip().lower() not in {"1", "true", "yes", "✔"}:
                continue
            segs.append({"start": float(row["start"]), "end": float(row["end"] )})
    Path(out_json).write_text(json.dumps(segs, indent=2))
    print(f"✅  {len(segs)} clip(s) flagged → {out_json}")


def identify_clips_json(edit_json: str = "segments_edit.json", out_json: str = "segments_to_keep.json") -> None:
    """Save segments with keep true in edit_json to JSON list."""
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


def extract_marked(markup: str = "markup_guide.txt", out_json: str = "segments_to_keep.json") -> None:
    """Parse markup_guide.txt and dump JSON segment list."""
    if not Path(markup).exists():
        sys.exit("❌  markup_guide.txt not found – run transcription first")
    segs, open_start = [], None
    for ln, line in enumerate(Path(markup).read_text().splitlines(), 1):
        line = line.strip()
        if line.startswith("[") and "-" in line:
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


def extract_segments_from_json(json_file: str, speaker_match: str, out_txt: str = "segments.txt"):
    data = json.loads(Path(json_file).read_text())
    segments = data.get("segments", data)

    output = []
    active = False

    for seg in segments:
        speaker = seg.get("label") or seg.get("speaker", "")
        if speaker_match.lower() in speaker.lower():
            start = round(seg["start"], 2)
            end = round(seg["end"], 2)
            text = seg.get("text", "").strip()

            if not active:
                output.append("=START=")
                active = True

            output.append(f"[{start}-{end}] {speaker}: {text}")

        elif active:
            output.append("=END=")
            active = False

    if active:
        output.append("=END=")

    Path(out_txt).write_text("\n".join(output))
    print(f"✅ wrote {out_txt} with {output.count('=START=')} segments")


def segments_json_to_txt(json_file: str, out_txt: str = "segments.txt") -> None:
    """Write a text representation of segments for manual editing."""
    if not Path(json_file).exists():
        sys.exit(f"❌  {json_file} not found")
    segs = json.loads(Path(json_file).read_text())
    if isinstance(segs, dict) and "segments" in segs:
        segs = segs["segments"]
    lines = []
    idx = 1
    for seg in segs:
        lines.append("=START=")
        for line in seg.get("text", []):
            if line.startswith("[") and "]" in line:
                line = line.split("]", 1)[1].strip()
            lines.append(f"\t[{idx}]{line}")
            idx += 1
        lines.append("=END=")
    Path(out_txt).write_text("\n".join(lines))
    print(f"✅  wrote {out_txt}")


def segments_from_txt(seg_txt: str) -> list[tuple[int, int]]:
    """Return ``[(start_idx, end_idx), ...]`` parsed from *seg_txt*."""
    entries: list[tuple[int, int]] = []
    cur: list[int] = []
    for raw in Path(seg_txt).read_text().splitlines():
        line = raw.strip()
        if line == "=START=":
            cur = []
        elif line == "=END=":
            if cur:
                entries.append((cur[0], cur[-1]))
            cur = []
        elif line.startswith("[") and "]" in line:
            num_str = line[1: line.find("]")]
            try:
                num = int(num_str)
            except ValueError:
                continue
            cur.append(num)
    return entries


def _parse_time(ts: str) -> float:
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _load_srt_entries(path: Path) -> list[dict]:
    entries: list[dict] = []
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        if lines[i].startswith("="):
            i += 1
            continue
        number = lines[i].strip()
        i += 1
        if i >= len(lines):
            break
        ts_line = lines[i].strip()
        i += 1
        if "-->" not in ts_line:
            continue
        start_str, end_str = [p.strip() for p in ts_line.split("-->")]
        start, end = _parse_time(start_str), _parse_time(end_str)
        while i < len(lines) and lines[i].strip():
            i += 1
        entries.append({"number": int(number), "start": start, "end": end})
        while i < len(lines) and not lines[i].strip():
            i += 1
    return entries


def load_segments(seg_file: str, srt_file: str | None = None) -> list[dict]:
    """Return ``[{start, end}, ...]`` from *seg_file* (txt or json)."""
    path = Path(seg_file)
    if not path.exists():
        sys.exit(f"❌  '{seg_file}' not found. Run identify-segments first.")
    if path.suffix == ".txt":
        if srt_file is None:
            srt_file = str(path.with_suffix(".srt"))
        if not Path(srt_file).exists():
            sys.exit(f"❌  SRT file '{srt_file}' required for segments.txt")
        numbers = segments_from_txt(seg_file)
        entries = _load_srt_entries(Path(srt_file))
        idx = {e["number"]: e for e in entries}
        segs: list[dict] = []
        for s, e in numbers:
            if s in idx and e in idx:
                segs.append({"start": idx[s]["start"], "end": idx[e]["end"]})
        return segs
    else:
        raw = json.loads(path.read_text())
        if isinstance(raw, dict) and "segments" in raw:
            raw = raw["segments"]
        try:
            segs = [
                {"start": float(s["start"]), "end": float(s["end"])}
                for s in raw
            ]
        except Exception:
            sys.exit(f"❌  Unexpected JSON format in '{seg_file}'.")
        return sorted(segs, key=lambda seg: seg["start"])

__all__ = [
    "json_to_tsv",
    "json_to_markup",
    "json_to_editable",
    "write_segments_txt_from_editable",
    "identify_clips",
    "identify_clips_json",
    "extract_marked",
    "extract_segments_from_json",
    "segments_json_to_txt",
    "segments_from_txt",
    "load_segments",
]

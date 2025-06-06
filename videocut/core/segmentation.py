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
                seg.get("speaker", ""),
                str(seg.get("text", "")).replace("\n", " "),
                "",
            ])
    print(f"✅  {len(segs)} segment(s) → {out_tsv}")


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
            speaker = seg.get("speaker", "")
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

__all__ = [
    "json_to_tsv",
    "json_to_editable",
    "identify_clips",
    "identify_clips_json",
    "extract_marked",
]

"""Transcript segmentation utilities."""
from __future__ import annotations
import csv
import json
import sys
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


def json_to_editable(json_path: str, out_json: str = "segments_edit.json") -> None:
    """Create an editable JSON with keep flag and context fields."""
    data = json.loads(Path(json_path).read_text())
    segs_in = data if isinstance(data, list) else data.get("segments", data)
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

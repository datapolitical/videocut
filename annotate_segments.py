#!/usr/bin/env python3
"""
annotate_segments.py

Read `markup_guide.txt` and `segments_to_keep.json`, then write
`markup_with_markers.txt` where each Nicholson segment is wrapped by
its own-line `{START}` and `{END}` markers.

Usage:
    python3 annotate_segments.py
"""

import json
import re
import sys
from pathlib import Path

MARKUP_IN   = Path("markup_guide.txt")
SEGMENTS_IN = Path("segments_to_keep.json")
MARKUP_OUT  = Path("markup_with_markers.txt")

# Matches lines beginning with “[start–end]”
_TS_RE = re.compile(r"^\s*\[(?P<start>\d+\.?\d*)[–-](?P<end>\d+\.?\d*)\]")

def load_segments(json_path: Path) -> list[dict]:
    if not json_path.exists():
        sys.exit(f"❌  '{json_path}' not found. Run auto-mark-nicholson first.")
    raw = json.loads(json_path.read_text())
    if isinstance(raw, dict) and "segments" in raw:
        raw = raw["segments"]
    try:
        segs = [{"start": float(s["start"]), "end": float(s["end"])} for s in raw]
    except Exception:
        sys.exit(f"❌  Unexpected JSON format in '{json_path}'.")
    return sorted(segs, key=lambda seg: seg["start"])

def load_markup(markup_path: Path) -> list[str]:
    if not markup_path.exists():
        sys.exit(f"❌  '{markup_path}' not found – run --transcribe first.")
    return markup_path.read_text().splitlines()

def parse_ts(line: str) -> tuple[float, float] | None:
    m = _TS_RE.match(line)
    if not m:
        return None
    return float(m.group("start")), float(m.group("end"))

def annotate(markup_lines: list[str], segments: list[dict]) -> list[str]:
    out: list[str] = []
    seg_idx = 0
    saw_start = False

    for line in markup_lines:
        ts = parse_ts(line)

        if ts is not None and seg_idx < len(segments):
            line_start, line_end = ts
            s = segments[seg_idx]["start"]
            e = segments[seg_idx]["end"]

            # If segment start falls within this line’s window, insert {START} on its own line
            if not saw_start and line_start <= s <= line_end:
                out.append(f"{{START}} [{s:.3f}–{e:.3f}]")
                saw_start = True

            # Append the transcript line itself
            out.append(line)

            # If we saw the START, and segment end falls within this line’s window, insert {END}
            if saw_start and line_start <= e <= line_end:
                out.append(f"{{END}}   [{s:.3f}–{e:.3f}]")
                seg_idx += 1
                saw_start = False

        else:
            out.append(line)

    # If any segments remain unmatched, append START/END at the bottom, each on its own line
    while seg_idx < len(segments):
        s = segments[seg_idx]["start"]
        e = segments[seg_idx]["end"]
        out.append(f"{{START}} [{s:.3f}–{e:.3f}]")
        out.append(f"{{END}}   [{s:.3f}–{e:.3f}]")
        seg_idx += 1

    return out


def annotate_segments(
    markup_file: str = "markup_guide.txt",
    seg_json: str = "segments_to_keep.json",
    out_file: str = "markup_with_markers.txt",
) -> None:
    """Write ``out_file`` with ``{START}``/``{END}`` markers for segments."""
    segments = load_segments(Path(seg_json))
    markup = load_markup(Path(markup_file))
    annotated = annotate(markup, segments)
    Path(out_file).write_text("\n".join(annotated))
    print(
        f"✅  Wrote annotated markup → {out_file} (with inline {{START}}/{{END}} on separate lines)"
    )


def main() -> None:
    annotate_segments()

if __name__ == "__main__":
    main()

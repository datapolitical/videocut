"""Markup annotation utilities."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path


_MARKUP_IN_DEFAULT = "markup_guide.txt"
_SEGMENTS_IN_DEFAULT = "segments_to_keep.json"
_MARKUP_OUT_DEFAULT = "markup_with_markers.txt"

_TS_RE = re.compile(r"^\s*\[(?P<start>\d+\.?\d*)[–-](?P<end>\d+\.?\d*)\]")


def load_segments(json_path: Path) -> list[dict]:
    """Load and sort clip segments from a JSON file."""
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
    """Return lines from ``markup_path`` or exit if missing."""
    if not markup_path.exists():
        sys.exit(f"❌  '{markup_path}' not found – run --transcribe first.")
    return markup_path.read_text().splitlines()


def parse_ts(line: str) -> tuple[float, float] | None:
    """Return ``(start, end)`` from transcript ``line`` or ``None``."""
    m = _TS_RE.match(line)
    if not m:
        return None
    return float(m.group("start")), float(m.group("end"))


def annotate(markup_lines: list[str], segments: list[dict]) -> list[str]:
    """Return ``markup_lines`` annotated with ``{START}``/``{END}`` markers."""
    out: list[str] = []
    seg_idx = 0
    saw_start = False

    for line in markup_lines:
        ts = parse_ts(line)

        if ts is not None and seg_idx < len(segments):
            line_start, line_end = ts
            s = segments[seg_idx]["start"]
            e = segments[seg_idx]["end"]

            if not saw_start and line_start <= s <= line_end:
                out.append(f"{START} [{s:.3f}–{e:.3f}]")
                saw_start = True

            out.append(line)

            if saw_start and line_start <= e <= line_end:
                out.append(f"{END}   [{s:.3f}–{e:.3f}]")
                seg_idx += 1
                saw_start = False
        else:
            out.append(line)

    while seg_idx < len(segments):
        s = segments[seg_idx]["start"]
        e = segments[seg_idx]["end"]
        out.append(f"{START} [{s:.3f}–{e:.3f}]")
        out.append(f"{END}   [{s:.3f}–{e:.3f}]")
        seg_idx += 1

    return out


START = "{START}"
END = "{END}"


def annotate_segments(
    markup_file: str = _MARKUP_IN_DEFAULT,
    seg_json: str = _SEGMENTS_IN_DEFAULT,
    out_file: str = _MARKUP_OUT_DEFAULT,
) -> None:
    """Write ``out_file`` with annotation markers for segments."""
    segments = load_segments(Path(seg_json))
    markup = load_markup(Path(markup_file))
    annotated = annotate(markup, segments)
    Path(out_file).write_text("\n".join(annotated))
    print(
        f"✅  Wrote annotated markup → {out_file} (with inline {START}/{END} markers)"
    )


__all__ = [
    "load_segments",
    "load_markup",
    "parse_ts",
    "annotate",
    "annotate_segments",
]

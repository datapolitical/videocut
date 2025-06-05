#!/usr/bin/env python3
"""auto_segment_nicholson.py

Generate segments_to_keep.json automatically for Secretary Nicholson
based on input diarization JSON.

Usage: python3 auto_segment_nicholson.py [input.json] [output.json]
"""
import json
import re
import sys
from pathlib import Path

# We'll import map_nicholson_speaker for fallback
from clip_utils import map_nicholson_speaker

TRAIL_SEC = 30  # trailing context after end
PRE_SEC = 5     # lines to capture before start

# Cues indicating the meeting moved on
_END_PATTERNS = [
    r"\bthank you\b",
    r"\bnext item\b",
    r"\bmove on\b",
    r"\bdirector\b",
    r"\bchair\b",
]
_END_RE = re.compile("|".join(_END_PATTERNS), re.IGNORECASE)

_TS_RE = re.compile(r"^\s*\[(?P<start>\d+\.?\d*)[–-](?P<end>\d+\.?\d*)\]\s*(?P<rest>.*)")

_ROLL_RE = re.compile(r"roll call", re.IGNORECASE)
_NICH_ITEM_RE = re.compile(r"nicholson", re.IGNORECASE)


def load_markup(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = []
    for line in path.read_text().splitlines():
        m = _TS_RE.match(line)
        if not m:
            continue
        lines.append({
            "start": float(m.group("start")),
            "end": float(m.group("end")),
            "line": line,
        })
    return lines


def collect_pre(segs: list[dict], start: float) -> list[str]:
    window = start - PRE_SEC
    return [s["line"] for s in segs if s["end"] <= start and s["end"] >= window]


def collect_post(segs: list[dict], end: float, next_start: float | None = None) -> list[str]:
    """Grab transcript lines following a segment.

    Lines are collected until either ``TRAIL_SEC`` seconds pass or the next
    Nicholson segment begins.
    """
    window = end + TRAIL_SEC
    out = []
    for l in segs:
        if l["start"] < end:
            continue
        if next_start is not None and l["start"] >= next_start:
            break
        if l["start"] > window:
            break
        out.append(l["line"])
    return out


def trim_segment(start: float, end: float, markup: list[dict]) -> tuple[float, list[str]]:
    """Trim roll calls unrelated to Nicholson."""
    lines = [l for l in markup if l["start"] < end and l["end"] > start]

    for l in lines:
        if _ROLL_RE.search(l["line"]):
            prev = [p for p in markup if p["end"] <= l["start"] and p["end"] >= l["start"] - 60]
            if not any(_NICH_ITEM_RE.search(p["line"]) for p in prev):
                end = min(end, l["start"])
                break

    trimmed = [l["line"] for l in markup if l["start"] < end and l["end"] > start]
    return end, trimmed


def should_end(text: str) -> bool:
    return bool(_END_RE.search(text))


def find_nicholson_speaker(segments):
    """Heuristic search for Nicholson's speaker ID."""
    cues = [
        "i have secretary nicholson",  # chair recognizes him next
        "thank you very much, secretary nicholson",  # responses to his question
        "nicholson, do i have",  # motion/second requests
    ]

    for i, seg in enumerate(segments):
        txt = seg.get("text", "").lower()
        if any(c in txt for c in cues):
            j = i + 1
            while j < len(segments) and segments[j]["speaker"] == seg["speaker"]:
                j += 1
            if j < len(segments):
                return segments[j]["speaker"]

    # Fallback: search for generic mentions and pick the last candidate
    candidate = None
    for i, seg in enumerate(segments):
        txt = seg.get("text", "").lower()
        if "nicholson" in txt:
            j = i + 1
            while j < len(segments) and segments[j]["speaker"] == seg["speaker"]:
                j += 1
            if j < len(segments):
                candidate = segments[j]["speaker"]
    return candidate


def main() -> None:
    in_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("input.json")
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("segments_to_keep.json")
    markup_path = in_path.with_name("markup_guide.txt")

    data = json.loads(in_path.read_text())
    segs = data["segments"]
    markup_lines = load_markup(markup_path)

    nicholson_id = find_nicholson_speaker(segs)
    if nicholson_id is None:
        nicholson_id = map_nicholson_speaker(str(in_path))

    print(f"🔍  Secretary Nicholson identified as {nicholson_id}")

    results = []

    # Build list of indices where Nicholson speaks
    n_idx = [i for i, seg in enumerate(segs) if seg.get("speaker") == nicholson_id]
    if not n_idx:
        out_path.write_text("[]")
        print("❌  No Nicholson segments found")
        return

    groups = []
    start_idx = n_idx[0]
    last_idx = n_idx[0]
    for idx in n_idx[1:]:
        prev_end = float(segs[last_idx]["end"])
        cur_start = float(segs[idx]["start"])
        if cur_start - prev_end >= 120:
            groups.append((start_idx, last_idx))
            start_idx = idx
        last_idx = idx
    groups.append((start_idx, last_idx))

    for start_idx, last_idx in groups:
        start_time = float(segs[start_idx]["start"])
        end_time = float(segs[last_idx]["end"])

        j = last_idx + 1
        while j < len(segs):
            seg = segs[j]
            if seg.get("speaker") == nicholson_id:
                break
            if float(seg["start"]) - end_time >= 120 and should_end(seg.get("text", "")):
                end_time = float(seg["end"])
                break
            end_time = float(seg["end"])
            j += 1

        if j < len(segs):
            next_start = float(segs[j]["start"])
            end_time = min(end_time + TRAIL_SEC, next_start)
        else:
            next_start = None
            end_time = end_time + TRAIL_SEC

        end_time, segment_lines = trim_segment(start_time, end_time, markup_lines)
        pre_lines = collect_pre(markup_lines, start_time)
        post_lines = collect_post(markup_lines, end_time, next_start)

        results.append({
            "start": round(start_time, 2),
            "end": round(end_time, 2),
            "text": segment_lines,
            "pre": pre_lines,
            "post": post_lines,
        })

    out_path.write_text(json.dumps(results, indent=2))
    print(f"✅  {len(results)} segments → {out_path}")


if __name__ == "__main__":
    main()

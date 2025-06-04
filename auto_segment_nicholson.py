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

# Cues indicating the meeting moved on
_END_PATTERNS = [
    r"\bthank you\b",
    r"\bnext item\b",
    r"\bmove on\b",
    r"\bdirector\b",
    r"\bchair\b",
]
_END_RE = re.compile("|".join(_END_PATTERNS), re.IGNORECASE)


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
    return None


def main() -> None:
    in_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("input.json")
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("segments_to_keep.json")

    data = json.loads(in_path.read_text())
    segs = data["segments"]

    nicholson_id = find_nicholson_speaker(segs)
    if nicholson_id is None:
        nicholson_id = map_nicholson_speaker(str(in_path))

    print(f"🔍  Secretary Nicholson identified as {nicholson_id}")

    results = []
    start = None
    last_end = None

    for idx, seg in enumerate(segs):
        spk = seg.get("speaker")
        s = float(seg["start"])
        e = float(seg["end"])
        text = seg.get("text", "")

        if start is None:
            # Nicholson begins substantial remarks
            if spk == nicholson_id and len(text.split()) > 7:
                start = s
                last_end = e
            # Chair calls on Nicholson by name
            elif spk != nicholson_id and "secretary" in text.lower():
                nxt = next((seg2 for seg2 in segs[idx+1:idx+6] if seg2["speaker"] == nicholson_id and len(seg2["text"].split()) > 7), None)
                if nxt and nxt["start"] - s <= 10:
                    if nxt["start"] - s > 5:
                        start = nxt["start"]
                    else:
                        start = max(0.0, s - 2)
                    last_end = nxt["end"]
        else:
            if spk == nicholson_id:
                last_end = e
            else:
                next_nich = next((seg2 for seg2 in segs[idx:] if seg2["speaker"] == nicholson_id), None)
                silence = next_nich["start"] - e if next_nich else float("inf")
                if silence >= 120 and should_end(text):
                    results.append({"start": round(start, 2), "end": round(e, 2)})
                    start = None
                    last_end = None

    if start is not None and last_end is not None:
        results.append({"start": round(start, 2), "end": round(last_end, 2)})

    out_path.write_text(json.dumps(results, indent=2))
    print(f"✅  {len(results)} segments → {out_path}")


if __name__ == "__main__":
    main()

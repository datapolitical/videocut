"""Utilities for summarizing kept clip transcripts."""
from __future__ import annotations
import json
import re
from pathlib import Path
from . import segmentation


_TS_RE = re.compile(r"\[(?P<start>\d+\.?\d*)[–-](?P<end>\d+\.?\d*)")


def parse_line(line: str) -> dict | None:
    """Parse ``[start-end] text`` lines from ``markup_guide.txt``."""
    if line.startswith("[") and "]" in line:
        ts_part, rest = line.split("]", 1)
        m = _TS_RE.match(ts_part)
        if not m:
            return None
        start = float(m.group("start"))
        end = float(m.group("end"))
        return {"start": start, "end": end, "text": rest.strip()}
    return None


def clip_transcripts(
    markup_file: str = "markup_guide.txt",
    seg_file: str = "segments.txt",
    out_file: str = "clip_transcripts.txt",
    srt_file: str | None = None,
) -> None:
    """Write ``out_file`` listing transcript snippets for kept clips."""
    segments = segmentation.load_segments(seg_file, srt_file)
    lines = Path(markup_file).read_text().splitlines()
    entries = [e for l in lines if (e := parse_line(l))]

    clips = []
    for seg in segments:
        s, e = seg["start"], seg["end"]
        clip_entries = [ent for ent in entries if not (ent["end"] < s or ent["start"] > e)]
        full_text = " ".join(ent["text"] for ent in clip_entries)
        if len(full_text.split()) < 8:
            continue
        clips.append({"start": s, "end": e, "transcript": clip_entries})

    output_path = Path(out_file)
    with output_path.open("w") as out:
        for i, clip in enumerate(clips):
            out.write(f"=== Clip {i+1} ===\n")
            out.write(f"Start: {clip['start']:.2f} seconds\n")
            out.write(f"End:   {clip['end']:.2f} seconds\n")
            out.write("Transcript:\n")
            for entry in clip["transcript"]:
                out.write(f"  [{entry['start']:.2f}–{entry['end']:.2f}] {entry['text']}\n")
            out.write("\n")
    print(f"✅  Wrote {len(clips)} long clip transcripts to {output_path}")


__all__ = ["parse_line", "clip_transcripts"]

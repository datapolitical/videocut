"""Extract transcript snippets for each retained clip."""

import json
import re
from pathlib import Path


def parse_line(line: str) -> dict | None:
    """Parse ``[start-end] text`` lines from ``markup_guide.txt``."""
    if line.startswith("[") and "]" in line:
        ts_part, rest = line.split("]", 1)
        m = re.match(r"\[(?P<start>\d+\.?\d*)[–-](?P<end>\d+\.?\d*)", ts_part)
        if not m:
            return None
        start = float(m.group("start"))
        end = float(m.group("end"))
        return {"start": start, "end": end, "text": rest.strip()}
    return None

def main() -> None:
    """Write ``clip_transcripts.txt`` for the segments marked to keep."""

    segments = json.loads(Path("segments_to_keep.json").read_text())
    lines = Path("markup_guide.txt").read_text().splitlines()

    entries = [parse_line(line) for line in lines if parse_line(line)]

    clips = []
    for seg in segments:
        s, e = seg["start"], seg["end"]
        clip_entries = [
            entry for entry in entries
            if not (entry["end"] < s or entry["start"] > e)
        ]
        full_text = " ".join(entry["text"] for entry in clip_entries)

        word_count = len(full_text.split())
        if word_count < 8:
            continue

        clips.append({"start": s, "end": e, "transcript": clip_entries})

    output_path = Path("clip_transcripts.txt")
    with output_path.open("w") as out:
        for i, clip in enumerate(clips):
            out.write(f"=== Clip {i+1} ===\n")
            out.write(f"Start: {clip['start']:.2f} seconds\n")
            out.write(f"End:   {clip['end']:.2f} seconds\n")
            out.write("Transcript:\n")
            for entry in clip["transcript"]:
                out.write(
                    f"  [{entry['start']:.2f}–{entry['end']:.2f}] {entry['text']}\n"
                )
            out.write("\n")

    print(f"✅  Wrote {len(clips)} long clip transcripts to {output_path}")


if __name__ == "__main__":
    main()

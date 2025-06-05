import json
import re
from pathlib import Path


def parse_line(line: str) -> dict | None:
    if line.startswith("[") and "]" in line:
        ts_part, rest = line.split("]", 1)
        m = re.match(r"\[(?P<start>\d+\.?\d*)[–-](?P<end>\d+\.?\d*)", ts_part)
        if not m:
            return None
        start = float(m.group("start"))
        end = float(m.group("end"))
        return {"start": start, "end": end, "text": rest.strip()}
    return None

def clip_transcripts(
    seg_json: str = "segments_to_keep.json",
    markup_file: str = "markup_guide.txt",
    out_txt: str = "clip_transcripts.txt",
) -> None:
    """Write a transcript summary for each clip."""
    segments = json.loads(Path(seg_json).read_text())
    lines = Path(markup_file).read_text().splitlines()

    entries = [parse_line(line) for line in lines if parse_line(line)]

    clips = []
    for seg in segments:
        s, e = seg["start"], seg["end"]
        clip_entries = [entry for entry in entries if not (entry["end"] < s or entry["start"] > e)]
        full_text = " ".join(entry["text"] for entry in clip_entries)

        # Skip clips that are too short or contain only brief interjections
        if len(full_text.split()) < 8:
            continue

        clips.append({"start": s, "end": e, "transcript": clip_entries})

    output_path = Path(out_txt)
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


def main() -> None:
    clip_transcripts()


if __name__ == "__main__":
    main()

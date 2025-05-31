#!/usr/bin/env python3
import re
import json
import subprocess
import sys
from pathlib import Path

def parse_timestamp(ts_text: str):
    """
    Given a string like "[123.45–130.00]" (or using a hyphen "-"),
    strip off the brackets, replace any en-dashes with hyphens, then split.
    Returns (start: float, end: float).
    """
    ts_text = ts_text.strip()
    if ts_text.startswith("[") and ts_text.endswith("]"):
        ts_text = ts_text[1:-1]
    ts_text = ts_text.replace("–", "-")
    try:
        start_s, end_s = ts_text.split("-")
        return float(start_s), float(end_s)
    except Exception:
        raise ValueError(f"Could not parse timestamp '{ts_text}'")


def extract_marked(markup_file="markup_guide.txt", out_json="segments_to_keep.json"):
    """
    Reads through markup_file line by line. Whenever it sees a line that is exactly "START",
    it will take the next non-empty line (even if that line has extra text after the timestamp)
    as the start‐timestamp. Whenever it sees a line that is exactly "END", it will take the next
    non-empty line as the end‐timestamp, and append that (start,end) pair to the output list.
    """
    segments = []
    current_start = None

    print("📂 Opening", markup_file, "…")
    with open(markup_file, "r", encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f.readlines()]
    print(f"📄 Loaded {len(lines)} lines from {markup_file}")

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # If we see exactly "START", look ahead for the next non-empty line
        if line == "START":
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                next_line = lines[j].strip()
                # Match “[number–number]” at start, ignoring any trailing text
                m = re.match(r"^\s*\[(\d+\.\d+)[–-](\d+\.\d+)\]", next_line)
                if m:
                    start_ts = float(m.group(1))
                    end_ts   = float(m.group(2))
                    current_start = start_ts
                    print(f"🔍 Found START at line {i}: Next timestamp [{start_ts}–{end_ts}] → set current_start={start_ts}")
                else:
                    print(f"⚠️ Expected a timestamp after START at line {i}, but saw: '{next_line}'")
                i = j  # skip ahead to that timestamp line
            else:
                print(f"⚠️ 'START' at line {i} has no following timestamp line!")
            i += 1
            continue

        # If we see exactly "END" and have a current_start, look ahead for the next non-empty line
        if line == "END" and current_start is not None:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                next_line = lines[j].strip()
                m = re.match(r"^\s*\[(\d+\.\d+)[–-](\d+\.\d+)\]", next_line)
                if m:
                    start_ts = float(m.group(1))
                    end_ts   = float(m.group(2))
                    if start_ts != current_start:
                        print(f"⚠️ Mismatch: START was {current_start} but END timestamp at line {j} is {start_ts}")
                    segments.append({"start": current_start, "end": end_ts})
                    print(f"🔚 Found END at line {i}: Closing segment ({current_start}, {end_ts})")
                    current_start = None
                else:
                    print(f"⚠️ Expected a timestamp after END at line {i}, but saw: '{next_line}'")
                i = j
            else:
                print(f"⚠️ 'END' at line {i} has no following timestamp line!")
            i += 1
            continue

        i += 1

    if current_start is not None:
        print(f"⚠️ Warning: There was a START at {current_start} with no matching END.")

    with open(out_json, "w", encoding="utf-8") as f_out:
        json.dump(segments, f_out, indent=2)

    print(f"✅ Total segments extracted: {len(segments)}")
    print(f"✅ Extracted segments written to {out_json}")


def generate_clips(input_video, segments_json="segments_to_keep.json"):
    """
    Given an input video (e.g. input.mp4) and a JSON of {"start":X, "end":Y} segments,
    run ffmpeg to cut each segment into a separate file.
    """
    with open(segments_json, "r", encoding="utf-8") as f:
        segments = json.load(f)

    Path("clips").mkdir(exist_ok=True)
    for idx, seg in enumerate(segments):
        start = seg["start"]
        end   = seg["end"]
        outname = f"clips/clip_{idx:03d}.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start:.3f}",
            "-to", f"{end:.3f}",
            "-i", input_video,
            "-c", "copy", outname
        ]
        print(f"🎬 Creating {outname} from {start:.3f} to {end:.3f}")
        subprocess.run(cmd, check=True)


def concatenate(clips_dir="clips", output_file="final_output.mp4"):
    """
    Concatenate all the clip_###.mp4 files (in lex order) into a single output_file.
    Assumes ffmpeg concat demuxer format.
    """
    files = sorted(Path(clips_dir).glob("clip_*.mp4"))
    with open("to_concat.txt", "w", encoding="utf-8") as f:
        for p in files:
            f.write(f"file '{p.as_posix()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", "to_concat.txt",
        "-c", "copy", output_file
    ]
    print(f"🔗 Concatenating {len(files)} clips into {output_file}")
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Process and splice video by transcript markers")
    parser.add_argument("--input",      help="Input video file (e.g. input.mp4)", required=True)
    parser.add_argument("--hf_token",   help="HuggingFace token for diarization (optional)")
    parser.add_argument("--diarize",    action="store_true", help="Run transcription + diarization steps")
    parser.add_argument("--transcribe", action="store_true", help="Run only transcription step")
    parser.add_argument("--extract-marked", action="store_true", help="Extract segments based on START/END markers")
    parser.add_argument("--generate-clips", action="store_true", help="Run ffmpeg to generate individual clip files")
    parser.add_argument("--concatenate", action="store_true", help="Concatenate all clips into one output")
    args = parser.parse_args()

    if args.extract_marked:
        extract_marked()

    if args.generate_clips:
        generate_clips(args.input)

    if args.concatenate:
        concatenate()

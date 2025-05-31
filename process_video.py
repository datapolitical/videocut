#!/usr/bin/env python3
import os
import re
import json
import subprocess
import sys
from pathlib import Path
import shutil


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

# ── ffprobe helpers ────────────────────────────────────────────────────
def ffprobe_one(path: Path, select: str, field: str) -> str:
    """Return a single ffprobe field for the first stream that matches."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", select,
        "-show_entries", f"stream={field}",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout.strip()

def probe_props(clip: Path):
    """Return width, height, fps (as ratio), duration (float seconds)."""
    width   = ffprobe_one(clip, "v:0", "width")
    height  = ffprobe_one(clip, "v:0", "height")
    fps_raw = ffprobe_one(clip, "v:0", "avg_frame_rate")   # e.g. 30000/1001
    # Reduce ratio to float with 3 decimals (good enough for frame rate)
    num, den = (int(x) for x in fps_raw.split("/"))
    fps = round(num / den, 3)
    dur = float(ffprobe_one(clip, "v:0", "duration"))
    return dict(width=width, height=height, fps=fps, duration=dur)

# ── fade-wrapper helper ────────────────────────────────────────────────
def build_faded_clip(src: Path, dst: Path, props, fade_dur=0.25):
    """
    Render `src` into `dst`, adding:
        • fade-IN from white for first  fade_dur  seconds
        • fade-OUT to white for last   fade_dur  seconds
    """
    st_out = round(props["duration"] - fade_dur, 3)        # fade-out starts here
    w, h, fps = props["width"], props["height"], props["fps"]

    # second input: a solid-white clip (no pad label here!)
    white_input = [
        "-f", "lavfi",
        "-i", f"color=white:s={w}x{h}:r={fps}:d={props['duration']}"
    ]

    # filter graph:
    #   0:v  → add alpha fades            → [vfade]
    #   1:v  → solid white background     → (kept as [1:v])
    #   overlay white + video-with-alpha  → [vo]
    fv = (
        f"[0:v]format=yuva420p,"
        f"fade=t=in:st=0:d={fade_dur}:alpha=1,"
        f"fade=t=out:st={st_out}:d={fade_dur}:alpha=1[vfade]"
    )
    filter_complex = f"{fv};[1:v][vfade]overlay[vo]"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),               # input 0: real clip
        *white_input,                 # input 1: white background
        "-filter_complex", filter_complex,
        "-map", "[vo]",
        "-map", "0:a?",               # keep original audio if present
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(dst)
    ]
    subprocess.run(cmd, check=True)

# ── main routine ───────────────────────────────────────────────────────
def concatenate():
    clips_dir = Path("clips")
    raw_clips = sorted(clips_dir.glob("clip_*.mp4"))
    if not raw_clips:
        print("❌ No clips found in clips/*.mp4"); sys.exit(1)

    work_dir = Path("_faded")
    if work_dir.exists(): shutil.rmtree(work_dir)
    work_dir.mkdir()

    # 1) Pre-process each clip with fade-in/out
    faded = []
    for i, clip in enumerate(raw_clips, 1):
        props = probe_props(clip)
        out = work_dir / f"faded_{i:03}.mp4"
        build_faded_clip(clip, out, props)
        faded.append(out)

    # 2) Build ffmpeg concat via filter_complex (stream-safe)
    cmd = ["ffmpeg", "-y"]
    for f in faded:
        cmd += ["-i", str(f)]

    n = len(faded)
    # build [0:v][0:a][1:v][1:a]… concat
    pairs = "".join(f"[{i}:v][{i}:a]" for i in range(n))
    concat = f"{pairs}concat=n={n}:v=1:a=1[outv][outa]"

    cmd += ["-filter_complex", concat, "-map", "[outv]", "-map", "[outa]", "final_fade_white.mp4"]

    subprocess.run(cmd, check=True)
    print("✅ final_fade_white.mp4 created with smooth white fades!")

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

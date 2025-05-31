#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import argparse
import re
from pathlib import Path
from datetime import datetime

# If using HuggingFace for diarization/transcription, ensure transformers is installed:
# pip install transformers torchaudio pydub

###############################################################################
# Helper: Probe resolution of a video file using ffprobe
###############################################################################
def probe_resolution(filename):
    """
    Uses ffprobe to return (width, height) of the given video file.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json",
        filename
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(proc.stdout)
    stream = info["streams"][0]
    return int(stream["width"]), int(stream["height"])


###############################################################################
# Helper: Create a 0.5-second white flash of matching resolution
###############################################################################
def create_white_flash(duration, resolution, out_filename="white_flash.mp4"):
    """
    Create a solid-white video of given resolution (e.g. "1280x720") & duration.
    """
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=white:s={resolution}:d={duration}",
        "-c:v", "libx264",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        out_filename
    ]
    subprocess.run(cmd, check=True)


###############################################################################
# Helper: Build concat_list.txt interleaving clips with white_flash
###############################################################################
def build_concat_list(clips_folder="clips", white_flash="white_flash.mp4", list_filename="concat_list.txt"):
    """
    Scans clips_folder for clip_*.mp4, and interleaves white_flash between each.
    Writes a file listing (in ffmpeg concat format) to list_filename.
    """
    clips = sorted([
        f for f in os.listdir(clips_folder)
        if f.startswith("clip_") and f.endswith(".mp4")
    ])
    with open(list_filename, "w") as fh:
        for idx, clip in enumerate(clips):
            fh.write(f"file '{os.path.join(clips_folder, clip)}'\n")
            if idx < len(clips) - 1:
                fh.write(f"file '{white_flash}'\n")


###############################################################################
# Helper: Run ffmpeg concat demuxer on the given list file
###############################################################################
def run_concat(list_filename="concat_list.txt", output="output_with_flash.mp4"):
    """
    Runs ffmpeg concat demuxer on the given list file.
    """
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_filename,
        "-c", "copy",
        output
    ]
    subprocess.run(cmd, check=True)


###############################################################################
# Step 1: (Re)generate transcription with diarization
###############################################################################
def transcribe_and_diarize(input_file, hf_token=None):
    """
    1) Extracts audio from input_file as WAV
    2) Runs diarization to label speaker segments
    3) Runs transcription on each segment and outputs a combined transcript
    Saves results as 'transcript.json' with:
      {
        "segments": [
          { "start": float, "end": float, "speaker": "SPEAKER_1", "text": "..." },
          ...
        ]
      }
    """
    WORKDIR = "diarize_work"
    os.makedirs(WORKDIR, exist_ok=True)

    # 1) Extract audio
    audio_path = os.path.join(WORKDIR, "extracted.wav")
    cmd_extract = [
        "ffmpeg", "-y",
        "-i", input_file,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        audio_path
    ]
    print(f"🎤 Extracting audio to {audio_path}")
    subprocess.run(cmd_extract, check=True)

    # 2) Run speaker diarization (requires pyannote.audio or similar).
    #    Here we assume you have a pre-trained Pyannote model accessible via HF.
    try:
        from pyannote.audio import Pipeline
    except ImportError:
        print("❌ pyannote.audio not installed. Please install with 'pip install pyannote.audio'")
        sys.exit(1)

    print("🔊 Running speaker diarization...")
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization",
        use_auth_token=hf_token
    )
    diarization = pipeline(audio_path)

    # Collect diarization segments
    speaker_segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        speaker_segments.append({
            "start": turn.start,
            "end": turn.end,
            "speaker": speaker
        })

    # 3) Transcribe each speaker segment with Whisper (or HuggingFace)
    #    We'll use HuggingFace's "openai/whisper" pipeline here.
    try:
        from transformers import pipeline as hf_pipeline
    except ImportError:
        print("❌ transformers not installed. Please install with 'pip install transformers'")
        sys.exit(1)

    print("📝 Running transcription on each speaker segment...")
    whisper = hf_pipeline(
        "automatic-speech-recognition",
        model="openai/whisper-large-v2",
        chunk_length_s=30,
        device="cpu" if hf_token is None else "cuda",
        use_auth_token=hf_token
    )

    transcript_segments = []
    for idx, seg in enumerate(speaker_segments):
        start = seg["start"]
        end = seg["end"]
        # Extract that exact segment to a temp file
        tmp_clip = os.path.join(WORKDIR, f"seg_{idx:03d}.wav")
        cmd_clip = [
            "ffmpeg", "-y",
            "-i", audio_path,
            "-ss", str(start),
            "-to", str(end),
            "-c", "copy",
            tmp_clip
        ]
        subprocess.run(cmd_clip, check=True)
        # Transcribe
        result = whisper(tmp_clip)
        text = result["text"].strip()
        transcript_segments.append({
            "start": start,
            "end": end,
            "speaker": seg["speaker"],
            "text": text
        })
        print(f"   ▶ Segment {idx:03d} [{start:.2f}–{end:.2f}] ({seg['speaker']}) → \"{text[:30]}...\"")

    # Save combined transcript
    out_json = {"segments": transcript_segments}
    with open("transcript.json", "w") as f:
        json.dump(out_json, f, indent=2)
    print("✅ Transcription + diarization saved to transcript.json")


###############################################################################
# Step 2: Extract marked segments from markup_guide.txt
###############################################################################
def extract_marked():
    """
    Reads 'markup_guide.txt', finds lines containing 'START' or 'END' and matching timestamp lines,
    then writes out 'segments_to_keep.json' listing [start, end] pairs.
    """
    MARKUP = "markup_guide.txt"
    SEGMENTS_OUT = "segments_to_keep.json"
    if not os.path.isfile(MARKUP):
        print(f"❌ Cannot find {MARKUP}")
        sys.exit(1)

    segments = []
    current_start = None

    lines = open(MARKUP, "r").read().splitlines()
    print(f"📄 Loaded {len(lines)} lines from {MARKUP}")

    # Regex to match timestamps like "[123.45–678.90]"
    ts_pattern = re.compile(r"\[?(\d+\.\d+)[–-](\d+\.\d+)\]?")

    for idx, line in enumerate(lines):
        line = line.strip()
        if "START" in line:
            # Scan forward for the next timestamp
            for look_ahead in range(idx + 1, len(lines)):
                ma = ts_pattern.search(lines[look_ahead])
                if ma:
                    start_val = float(ma.group(1))
                    current_start = start_val
                    print(f"🔍 Found START at line {idx}: Next timestamp {ma.group(0)} → set current_start={current_start}")
                    break
        elif "END" in line and current_start is not None:
            # Scan forward for the next timestamp
            for look_ahead in range(idx + 1, len(lines)):
                ma = ts_pattern.search(lines[look_ahead])
                if ma:
                    end_val = float(ma.group(2))
                    if end_val <= current_start:
                        print(f"⚠️  Mismatch: START was {current_start} but END timestamp is earlier or equal: {end_val}")
                    segments.append([current_start, end_val])
                    print(f"🔚 Found END at line {idx}: Closing segment ({current_start}, {end_val})")
                    current_start = None
                    break

    print(f"✅ Total segments extracted: {len(segments)}")
    with open(SEGMENTS_OUT, "w") as f:
        json.dump(segments, f, indent=2)
    print(f"✅ Extracted segments written to {SEGMENTS_OUT}")


###############################################################################
# Step 3: Generate individual clips from segments_to_keep.json
###############################################################################
def generate_clips(input_file):
    """
    Reads 'segments_to_keep.json', then for each [start, end], runs ffmpeg to extract:
      clips/clip_000.mp4, clip_001.mp4, ...
    """
    SEGMENTS_IN = "segments_to_keep.json"
    CLIP_DIR = "clips"
    if not os.path.isfile(SEGMENTS_IN):
        print(f"❌ Cannot find {SEGMENTS_IN}. Did you run --extract-marked?")
        sys.exit(1)

    with open(SEGMENTS_IN, "r") as f:
        segments = json.load(f)

    os.makedirs(CLIP_DIR, exist_ok=True)
    for idx, (start, end) in enumerate(segments):
        out_name = os.path.join(CLIP_DIR, f"clip_{idx:03d}.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-i", input_file,
            "-ss", str(start),
            "-to", str(end),
            "-c", "copy",
            out_name
        ]
        print(f"🎬 Creating {out_name} from {start} to {end}")
        subprocess.run(cmd, check=True)
    print(f"✅ Generated {len(segments)} clips in '{CLIP_DIR}/'")


###############################################################################
# Main entry: dispatch based on flags
###############################################################################
def main():
    parser = argparse.ArgumentParser(description="Process video: diarize/transcribe, extract, clip, and concatenate with flash.")
    parser.add_argument("--input", "-i", help="Path to input video (e.g. input.mp4)")
    parser.add_argument("--hf_token", help="HuggingFace token (if required for private models)", default=None)

    parser.add_argument("--diarize", action="store_true", help="Run speaker diarization + transcription")
    parser.add_argument("--extract-marked", action="store_true", help="Extract [START-END] segments to JSON")
    parser.add_argument("--generate-clips", action="store_true", help="Generate clips/*.mp4 from segments_to_keep.json")
    parser.add_argument("--concatenate", action="store_true", help="Concatenate clips with half-second white flash transitions")

    args = parser.parse_args()

    if args.diarize:
        if not args.input:
            print("❌ --diarize requires --input <video>")
            sys.exit(1)
        transcribe_and_diarize(args.input, hf_token=args.hf_token)

    if args.extract_marked:
        extract_marked()

    if args.generate_clips:
        if not args.input:
            print("❌ --generate-clips requires --input <video>")
            sys.exit(1)
        generate_clips(args.input)

    if args.concatenate:
        # 1) Probe resolution from the first clip (if it exists), else fallback to probing the original input.
        try:
            sample = "clips/clip_000.mp4"
            if os.path.isfile(sample):
                w, h = probe_resolution(sample)
            elif args.input:
                w, h = probe_resolution(args.input)
            else:
                raise FileNotFoundError
            resolution = f"{w}x{h}"
        except Exception as e:
            print(f"⚠️  Could not probe resolution from clips or input: {e}")
            resolution = "1280x720"  # fallback

        # 2) Create a 0.5s white flash matching that size
        duration = 0.5
        create_white_flash(duration=duration, resolution=resolution, out_filename="white_flash.mp4")
        print(f"✅ white_flash.mp4 ({resolution}, {duration}s) created.")

        # 3) Build concat_list.txt to interleave clips with white_flash
        build_concat_list(clips_folder="clips", white_flash="white_flash.mp4", list_filename="concat_list.txt")
        print("✅ concat_list.txt written (clips + white flashes).")

        # 4) Run ffmpeg concat to produce final video
        run_concat(list_filename="concat_list.txt", output="final_with_flash.mp4")
        print("✅ final_with_flash.mp4 generated with half-second white transitions.")

    # If no flags are given, show help
    if not any([args.diarize, args.extract_marked, args.generate_clips, args.concatenate]):
        parser.print_help()


if __name__ == "__main__":
    main()

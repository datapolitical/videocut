#!/usr/bin/env python3
"""lightweight_process.py – orchestration CLI for the video pipeline."""

import argparse
import os
from dotenv import load_dotenv

from transcribe import transcribe
from clip_utils import (
    identify_clips_json,
    extract_marked,
    auto_mark_nicholson,
    generate_clips,
    concatenate_clips,
)

load_dotenv()

def main():
    p = argparse.ArgumentParser("lightweight_process")
    p.add_argument(
        "--input", default="input.mp4", help="Input video file"
    )
    p.add_argument(
        "--hf_token", default=os.getenv("HF_TOKEN"), help="Hugging Face token for diarization"
    )
    p.add_argument(
        "--transcribe", action="store_true", help="Run WhisperX transcription"
    )
    p.add_argument(
        "--diarize", action="store_true", help="Enable speaker diarization"
    )
    p.add_argument(
        "--identify-clips-json", action="store_true", help="Parse segments_edit.json to JSON"
    )
    p.add_argument(
        "--extract-marked", action="store_true", help="Parse markup_guide.txt to JSON"
    )
    p.add_argument(
        "--auto-mark-nicholson", action="store_true", help="Auto-identify Nicholson segments from JSON"
    )
    p.add_argument(
        "--generate-clips", action="store_true", help="Cut clips from JSON list"
    )
    p.add_argument(
        "--concatenate", action="store_true", help="Stitch clips with white flashes"
    )
    args = p.parse_args()

    if args.transcribe:
        transcribe(args.input, args.hf_token, args.diarize)
    if args.identify_clips_json:
        identify_clips_json()
    if args.extract_marked:
        extract_marked()
    if args.auto_mark_nicholson:
        json_file = f"{os.path.splitext(args.input)[0]}.json"
        auto_mark_nicholson(json_file)
    if args.generate_clips:
        generate_clips(args.input)
    if args.concatenate:
        concatenate_clips()

    if not any([
        args.transcribe,
        args.identify_clips_json,
        args.extract_marked,
        args.auto_mark_nicholson,
        args.generate_clips,
        args.concatenate,
    ]):
        p.print_help()

if __name__ == "__main__":  # filename: lightweight_process.py
    main()

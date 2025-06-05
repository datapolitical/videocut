#!/usr/bin/env python3
"""process_video.py – thin CLI wrapping videocut.core utilities."""

import argparse
import os
from dotenv import load_dotenv

from videocut.core.transcribe import transcribe
from videocut.core.clip_utils import (
    identify_clips,
    extract_marked,
    generate_clips,
    concatenate_clips,
)

load_dotenv()


def main() -> None:
    p = argparse.ArgumentParser("process_video")
    p.add_argument("--input", default="input.mp4", help="Input video file")
    p.add_argument(
        "--hf_token",
        default=os.getenv("HF_TOKEN"),
        help="Hugging Face token for diarization",
    )
    p.add_argument("--transcribe", action="store_true", help="Run WhisperX")
    p.add_argument("--diarize", action="store_true", help="Use speaker diarization")
    p.add_argument(
        "--identify-clips",
        action="store_true",
        help="Parse input.tsv → segments_to_keep.json",
    )
    p.add_argument(
        "--extract-marked",
        action="store_true",
        help="Parse markup_guide.txt → segments_to_keep.json",
    )
    p.add_argument(
        "--generate-clips",
        action="store_true",
        help="Cut clips from segments_to_keep.json",
    )
    p.add_argument(
        "--concatenate",
        action="store_true",
        help="Join clips with white flashes",
    )

    args = p.parse_args()

    if args.transcribe:
        transcribe(args.input, args.hf_token, args.diarize)
    if args.identify_clips:
        identify_clips()
    if args.extract_marked:
        extract_marked()
    if args.generate_clips:
        generate_clips(args.input)
    if args.concatenate:
        concatenate_clips()

    if not any(
        [
            args.transcribe,
            args.identify_clips,
            args.extract_marked,
            args.generate_clips,
            args.concatenate,
        ]
    ):
        p.print_help()


if __name__ == "__main__":
    main()

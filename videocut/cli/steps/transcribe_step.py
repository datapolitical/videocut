#!/usr/bin/env python3
"""Step 1: run WhisperX transcription."""
import argparse
import os
from videocut.core.transcribe import transcribe


def main() -> None:
    p = argparse.ArgumentParser(description="Run WhisperX transcription")
    p.add_argument("--input", default="input.mp4", help="Input video file")
    p.add_argument("--hf_token", default=os.getenv("HF_TOKEN"), help="Hugging Face token")
    p.add_argument("--diarize", action="store_true", help="Use speaker diarization")
    args = p.parse_args()
    transcribe(args.input, args.hf_token, args.diarize)


if __name__ == "__main__":
    main()

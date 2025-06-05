import argparse
import os
from dotenv import load_dotenv

from videocut.core.transcribe import transcribe
from videocut.core.clip_utils import extract_marked, generate_clips, concatenate_clips

load_dotenv()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process and splice video by transcript markers")
    parser.add_argument("--input", type=str, default="input.mp4", help="Input video filename")
    parser.add_argument("--hf_token", type=str, default=os.getenv("HF_TOKEN"), help="Hugging Face token (from .env or CLI)")
    parser.add_argument("--diarize", action="store_true", help="Use speaker diarization (slower, requires token)")
    parser.add_argument("--transcribe", action="store_true", help="Transcribe with WhisperX")
    parser.add_argument("--extract-marked", action="store_true", help="Parse START/END-marked lines")
    parser.add_argument("--generate-clips", action="store_true", help="Cut video clips")
    parser.add_argument("--concatenate", action="store_true", help="Join video clips")

    args = parser.parse_args()

    if args.transcribe:
        transcribe(args.input, args.hf_token, args.diarize)
    if args.extract_marked:
        extract_marked()
    if args.generate_clips:
        generate_clips(args.input)
    if args.concatenate:
        concatenate_clips()

    if not (args.transcribe or args.extract_marked or args.generate_clips or args.concatenate):
        parser.print_help()

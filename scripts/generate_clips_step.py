#!/usr/bin/env python3
"""Step 5: cut clips from segments_to_keep.json."""
import argparse
from clip_utils import generate_clips


def main() -> None:
    p = argparse.ArgumentParser(description="Generate video clips from JSON segments")
    p.add_argument("--input", default="input.mp4", help="Input video file")
    p.add_argument("--json", default="segments_to_keep.json", help="Segments JSON file")
    p.add_argument("--out_dir", default="clips", help="Output directory")
    args = p.parse_args()
    generate_clips(args.input, args.json, args.out_dir)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Step: generate clip_transcripts.txt summary."""
import argparse
from clip_transcripts import clip_transcripts


def main() -> None:
    p = argparse.ArgumentParser(description="Create transcript summary per clip")
    p.add_argument("--segments", default="segments_to_keep.json", help="Segments JSON")
    p.add_argument("--markup", default="markup_guide.txt", help="Transcript markup file")
    p.add_argument("--out", default="clip_transcripts.txt", help="Output text file")
    args = p.parse_args()
    clip_transcripts(args.segments, args.markup, args.out)


if __name__ == "__main__":
    main()

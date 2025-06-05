#!/usr/bin/env python3
"""Step: insert {START}/{END} markers into markup_guide.txt."""
import argparse
from annotate_segments import annotate_segments


def main() -> None:
    p = argparse.ArgumentParser(description="Annotate markup with clip markers")
    p.add_argument("--markup", default="markup_guide.txt", help="Input markup file")
    p.add_argument("--segments", default="segments_to_keep.json", help="JSON segments file")
    p.add_argument("--out", default="markup_with_markers.txt", help="Output markup file")
    args = p.parse_args()
    annotate_segments(args.markup, args.segments, args.out)


if __name__ == "__main__":
    main()

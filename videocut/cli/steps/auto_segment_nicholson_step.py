#!/usr/bin/env python3
"""Step: advanced Nicholson segmentation with context heuristics."""
import argparse
from auto_segment_nicholson import segment_nicholson


def main() -> None:
    p = argparse.ArgumentParser(description="Auto-segment Nicholson with context")
    p.add_argument("json", help="WhisperX diarization JSON file")
    p.add_argument("--out", default="segments_to_keep.json", help="Output JSON file")
    args = p.parse_args()
    segment_nicholson(args.json, args.out)


if __name__ == "__main__":
    main()

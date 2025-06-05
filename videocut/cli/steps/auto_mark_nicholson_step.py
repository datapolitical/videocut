#!/usr/bin/env python3
"""Step 4: auto-identify Nicholson segments from WhisperX JSON."""
import argparse
from videocut.core.clip_utils import auto_mark_nicholson


def main() -> None:
    p = argparse.ArgumentParser(description="Auto-identify Nicholson segments from JSON")
    p.add_argument("json", help="WhisperX diarization JSON file")
    p.add_argument("--out", default="segments_to_keep.json", help="Output JSON file")
    args = p.parse_args()
    auto_mark_nicholson(args.json, args.out)


if __name__ == "__main__":
    main()

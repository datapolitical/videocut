#!/usr/bin/env python3
"""Step 3: parse markup_guide.txt to JSON segments."""
import argparse
from videocut.core.clip_utils import extract_marked


def main() -> None:
    p = argparse.ArgumentParser(description="Parse markup_guide.txt to JSON segments")
    p.add_argument("--markup", default="markup_guide.txt", help="Markup file")
    p.add_argument("--out", default="segments_to_keep.json", help="Output JSON file")
    args = p.parse_args()
    extract_marked(args.markup, args.out)


if __name__ == "__main__":
    main()

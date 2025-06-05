#!/usr/bin/env python3
"""Step 3 alternative: parse ``segments_edit.json`` to ``segments_to_keep.json``."""
import argparse
from clip_utils import identify_clips_json


def main() -> None:
    p = argparse.ArgumentParser(description="Parse editable JSON to clip segments")
    p.add_argument("--json", default="segments_edit.json", help="Editable JSON file")
    p.add_argument("--out", default="segments_to_keep.json", help="Output JSON")
    args = p.parse_args()
    identify_clips_json(args.json, args.out)


if __name__ == "__main__":
    main()

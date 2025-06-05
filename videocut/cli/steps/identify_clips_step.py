#!/usr/bin/env python3
"""Step 3: convert ``input.tsv`` (edited spreadsheet) to ``segments_to_keep.json``.

Run :mod:`videocut.cli.steps.json_to_tsv_step` first to generate the TSV from the transcription
JSON, mark rows to keep, then run this script.
"""
import argparse
from videocut.core.clip_utils import identify_clips


def main() -> None:
    p = argparse.ArgumentParser(description="Parse TSV to JSON segments")
    p.add_argument("--tsv", default="input.tsv", help="TSV file")
    p.add_argument("--out", default="segments_to_keep.json", help="Output JSON file")
    args = p.parse_args()
    identify_clips(args.tsv, args.out)


if __name__ == "__main__":
    main()

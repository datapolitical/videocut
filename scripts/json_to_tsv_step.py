#!/usr/bin/env python3
"""Step 2: convert WhisperX JSON to TSV with an empty ``keep`` column."""
import argparse
from clip_utils import json_to_tsv


def main() -> None:
    p = argparse.ArgumentParser(description="Create editable TSV from WhisperX JSON")
    p.add_argument("json", help="Input JSON file from WhisperX")
    p.add_argument("--out", default="input.tsv", help="Output TSV file")
    args = p.parse_args()
    json_to_tsv(args.json, args.out)


if __name__ == "__main__":
    main()

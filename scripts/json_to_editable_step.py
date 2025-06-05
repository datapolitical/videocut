#!/usr/bin/env python3
"""Step 2 alternative: convert WhisperX JSON into ``segments_edit.json``.

Each entry includes ``Timestamp``/``content``/``pre``/``post`` fields and a
numeric ``id`` along with ``start``/``end``/``speaker`` and ``keep`` flag.
"""
import argparse
from clip_utils import json_to_editable


def main() -> None:
    p = argparse.ArgumentParser(description="Create editable JSON from WhisperX output")
    p.add_argument("json", help="Input JSON file from WhisperX")
    p.add_argument("--out", default="segments_edit.json", help="Output editable JSON")
    args = p.parse_args()
    json_to_editable(args.json, args.out)


if __name__ == "__main__":
    main()

"""
Convert matched.json \u2192 tab-indented transcript.txt for `videocut segment`.
"""

import json
from pathlib import Path


def matched_to_txt(matched_json: str | Path,
                   out_txt: str | Path,
                   precision: int = 3) -> None:
    data = json.loads(Path(matched_json).read_text())

    def fmt(t: float) -> str:
        return f"{t:.{precision}f}"

    with Path(out_txt).open("w") as fh:
        for rec in data:
            if rec.get("start") is None:
                fh.write(f"# UNMATCHED: {rec['text']}\n")
                continue
            speaker, body = rec["text"].split(":", 1)
            fh.write(
                f"\t[{fmt(rec['start'])}-{fmt(rec['end'])}] "
                f"{speaker.strip()}: {body.strip()}\n"
            )

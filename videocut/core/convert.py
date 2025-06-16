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

            text = rec.get("text", "")
            if ":" in text:
                speaker, body = text.split(":", 1)
                speaker = speaker.strip()
                body = body.strip()
                line = f"{speaker}: {body}"
            else:
                line = text.strip()

            fh.write(
                f"\t[{fmt(rec['start'])}-{fmt(rec['end'])}] {line}\n"
            )

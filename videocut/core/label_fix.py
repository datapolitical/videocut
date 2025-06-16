"""
Fix speaker labels in a `matched_*.json` file produced by
videocut dtw-align / match.  Output format (one line per utterance):

    Speaker<TAB>[start-end]<TAB>utterance text
"""

from __future__ import annotations
import json, re
from pathlib import Path


# Speaker lines appear at the start of a sentence as ``Name: text``.  The
# colon is followed by a space, which avoids matching timestamps like ``7:00``.
label_rx = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 .',\-]{1,50}):\s+(.*)")


def labelify(
    matched_json: str | Path,
    out_path: str | Path,
    *,
    default_speaker: str = "Unknown",
) -> None:
    data = json.loads(Path(matched_json).read_text())
    last_speaker = default_speaker
    out_lines = []

    for rec in data:
        text = rec["text"].strip()
        m = label_rx.match(text)
        if m:
            speaker, body = m.group(1).strip(), m.group(2).strip()
            last_speaker = speaker
        else:
            speaker, body = last_speaker, text
        out_lines.append(
            f"{speaker}\t[{rec['start']:.3f}-{rec['end']:.3f}]\t{body}"
        )

    Path(out_path).write_text("\n".join(out_lines), encoding="utf-8")

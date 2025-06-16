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

def pdf_labels(pdf_path: str | Path) -> set[str]:
    """Return the set of speaker labels found in ``pdf_path``."""
    labels: set[str] = set()
    for line in Path(pdf_path).read_text().splitlines():
        m = label_rx.match(line.strip())
        if m:
            labels.add(m.group(1).strip())
    return labels

def validate_txt_labels(txt_path: str | Path, valid_labels: set[str]) -> bool:
    """Return True if all speaker labels in ``txt_path`` are valid."""
    bad: list[tuple[int, str]] = []
    for i, line in enumerate(Path(txt_path).read_text().splitlines(), 1):
        label = line.split("\t", 1)[0].strip()
        if label and label not in valid_labels:
            bad.append((i, label))

    if bad:
        print("⚠️  invalid speaker labels found:")
        for line_no, label in bad:
            print(f"  line {line_no}: '{label}' not in transcript")
    else:
        print("✅ all speaker labels valid")
    return not bad


def labelify(
    matched_json: str | Path,
    out_path: str | Path,
    *,
    default_speaker: str = "Unknown",
    valid_labels: set[str] | None = None,
) -> None:
    data = json.loads(Path(matched_json).read_text())
    last_speaker = default_speaker
    out_lines = []

    for rec in data:
        text = rec["text"].strip()
        m = label_rx.match(text)
        speaker, body = last_speaker, text
        if m:
            cand = m.group(1).strip()
            remainder = m.group(2).strip()
            if valid_labels and cand not in valid_labels:
                for lbl in valid_labels:
                    if cand.endswith(lbl):
                        cand = lbl
                        remainder = text.split(lbl + ":", 1)[1].strip()
                        break
                else:
                    pass
            if not valid_labels or cand in valid_labels:
                speaker, body = cand, remainder
                last_speaker = speaker
        out_lines.append(
            f"{speaker}\t[{rec['start']:.3f}-{rec['end']:.3f}]\t{body}"
        )

    Path(out_path).write_text("\n".join(out_lines), encoding="utf-8")

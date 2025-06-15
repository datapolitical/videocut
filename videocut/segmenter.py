#!/usr/bin/env python3
"""
segmenter.py - build segments.txt for Nicholson highlight reel

Rules summary:
  - glue-window = 60 seconds between Nicholson clips
  - input transcript lines may be flush left (no tabs)
  - every non-marker line in segments.txt is tab indented
  - fence markers "=START=" and "=END=" appear flush-left
"""
import re
import pathlib
from typing import List, Dict

NICH = "Chris Nicholson"
CHAIR = "Julien Bouquet"
GLUE = 30.0
GLUE_LINES = 5  # glue if <=4 lines between Nicholson segments

pat = re.compile(
    r"\[(?P<start>[^\]-]+)\s*-\s*(?P<end>[^\]]+)\]\s*(?P<spk>[^:]+):\s*(?P<txt>.*)"
)


def to_sec(ts: str) -> float:
    try:
        return float(ts)
    except ValueError:
        h, m, s = map(float, ts.split(":"))
        return h * 3600 + m * 60 + s


def load_rows(path: str = "transcript.txt") -> List[Dict[str, str]]:
    rows = []
    p = pathlib.Path(path)
    if not p.exists():
        return rows
    for raw in p.read_text().splitlines():
        m = pat.match(raw.lstrip("\t"))
        if not m:
            continue
        d = m.groupdict()
        d["raw"] = raw
        d["ss"] = to_sec(d["start"].strip())
        d["es"] = to_sec(d["end"].strip())
        rows.append(d)
    return rows


def build_segments(rows: List[Dict[str, str]]) -> List[str]:
    out: List[str] = []
    open_seg = False
    last_end = -1e9
    last_idx = -1
    last_end_marker: int | None = None

    i = 0
    while i < len(rows):
        r = rows[i]
        spk = r["spk"].strip()
        txt = r["txt"].strip()

        # normalize indentation for transcript line
        line = "\t" + r["raw"].lstrip("\t")

        # close segment just before chair hand-off
        if open_seg and spk == CHAIR:
            lower = txt.lower()
            if lower.startswith("director ") or "thank you, secretary" in lower:
                recog_director = False
                after = lower
                if "thank you, secretary" in lower:
                    after = lower.split("thank you, secretary", 1)[1]
                if after.strip().startswith("director ") or " director " in after:
                    recog_director = True
                elif i + 1 < len(rows):
                    nr = rows[i + 1]
                    if nr["spk"].strip() == CHAIR:
                        nxt = nr["txt"].strip().lower()
                        if nxt.startswith("director "):
                            recog_director = True
                if recog_director:
                    out.append("=END=")
                    last_end_marker = len(out) - 1
                    open_seg = False

        # check for substantive Nicholson line to open segment
        if spk == NICH:
            words = [w.strip(".,!?,") for w in txt.lower().split()]
            simple = {"thank", "thanks", "you", "chair", "bouquet"}
            substantive = len(words) > 3 or not set(words) <= simple
            has_enough_words = len(words) >= 10
            if substantive and has_enough_words:
                if not open_seg:
                    if last_end_marker is not None and (
                        r["ss"] - last_end <= GLUE or i - last_idx <= GLUE_LINES
                    ):
                        out.pop(last_end_marker)  # glue with previous
                    else:
                        out.append("=START=")
                    open_seg = True
                    last_end_marker = None
        # copy line
        out.append(line)

        # remember Nicholson end time
        if spk == NICH:
            words = [w.strip(".,!?,") for w in txt.lower().split()]
            simple = {"thank", "thanks", "you", "chair", "bouquet"}
            substantive = len(words) > 3 or not set(words) <= simple
            has_enough_words = len(words) >= 10
            if open_seg or (substantive and has_enough_words):
                last_end = r["es"]
                last_idx = i

        i += 1

    if open_seg:
        out.append("=END=")
    return out


def main():
    rows = load_rows()
    seg_lines = build_segments(rows)
    pathlib.Path("segments.txt").write_text("\n".join(seg_lines) + "\n")

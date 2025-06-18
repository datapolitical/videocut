#!/usr/bin/env python3
"""
segmenter.py - build segments.txt for Nicholson highlight reel
"""
import re
import pathlib
import json
import tempfile
from pathlib import Path
from typing import List, Dict
from videocut.core import chair as chair_mod

BOARD_FILE = pathlib.Path(__file__).resolve().parents[1] / "board_members.txt"
if BOARD_FILE.exists():
    BOARD = {ln.strip() for ln in BOARD_FILE.read_text().splitlines() if ln.strip()}
else:
    BOARD = set()
BOARD_LOWER = {n.lower() for n in BOARD}

NICH = "Chris Nicholson"
CHAIR_DEFAULT = "Julien Bouquet"
TITLES = ["director", "chair", "secretary", "treasurer"]
GLUE = 30.0
GLUE_LINES = 5  # glue if <=4 lines between Nicholson segments

pat = re.compile(
    r"\[(?P<start>[^\]-]+)\s*-\s*(?P<end>[^\]]+)\]\s*(?P<spk>[^:]+):\s*(?P<txt>.*)"
)
pat_labeled = re.compile(
    r"(?P<spk>[^\t]+)\t\[(?P<start>[^\]-]+)\s*-\s*(?P<end>[^\]]+)\]\t(?P<txt>.*)"
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
        stripped = raw.lstrip("\t")
        m = pat_labeled.match(stripped)
        if not m:
            m = pat.match(stripped)
        if not m:
            continue
        d = m.groupdict()
        d["raw"] = raw
        d["ss"] = to_sec(d["start"].strip())
        d["es"] = to_sec(d["end"].strip())
        rows.append(d)
    return rows


def detect_chair(rows: List[Dict[str, str]], debug: bool = False) -> str:
    """Return the speaker name most likely acting as chair."""
    segments = [
        {"speaker": r["spk"].strip(), "text": r["txt"].strip()}
        for r in rows
        if r.get("spk")
    ]
    if not segments:
        return CHAIR_DEFAULT
    with tempfile.NamedTemporaryFile("w+", delete=False) as tmp:
        json.dump({"segments": segments}, tmp)
        tmp.flush()
        tmp_path = Path(tmp.name)
    try:
        chair_name = chair_mod.identify_chair(str(tmp_path))
    except Exception:
        chair_name = CHAIR_DEFAULT
    finally:
        tmp_path.unlink(missing_ok=True)
    if debug:
        print(f"🔍  detected chair: {chair_name}")
    return chair_name

def build_segments(rows: List[Dict[str, str]], debug: bool = False) -> List[str]:
    chair_name = detect_chair(rows, debug=debug)
    if debug:
        print(f"Using chair \"{chair_name}\"")
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
        if open_seg and spk == chair_name:
            lower = txt.lower()
            after = lower
            for prefix in (
                "thank you, secretary",
                "thank you, chair",
                "thank you, treasurer",
            ):
                after = after.split(prefix, 1)[-1]

            recog_director = False

            if any(
                after.strip().startswith(f"{t} ") or f" {t} " in after
                for t in TITLES
            ):
                recog_director = True
            elif i + 1 < len(rows):
                next_spk = rows[i + 1]["spk"].strip()
                next_lower = next_spk.lower()
                if next_spk not in {chair_name, NICH} and next_lower in BOARD_LOWER:
                    if any(
                        f"{t} {part}" in lower
                        for part in next_lower.split()
                        for t in TITLES
                    ):
                        recog_director = True
                elif next_spk == chair_name:
                    nxt = rows[i + 1]["txt"].strip().lower()
                    if any(nxt.startswith(f"{t} ") for t in TITLES):
                        recog_director = True

            if recog_director:
                out.append("=END=")
                if debug:
                    print(f"Segment end at {r['ss']:.2f}s")
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
                        if debug:
                            print(f"Segment start at {r['ss']:.2f}s")
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
        if debug:
            print("Segment end at EOF")
    return out


def main(debug: bool = False):
    rows = load_rows()
    seg_lines = build_segments(rows, debug=debug)
    pathlib.Path("segments.txt").write_text("\n".join(seg_lines) + "\n")

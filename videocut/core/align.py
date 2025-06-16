"""
Three-stage PDF ⇆ WhisperX aligner.

Stages
------
1. primary     – word-level sliding window (high precision)
2. secondary   – sentence-text fuzzy window (robust fallback)
3. interpolated – timestamp interpolation if everything else fails

API  ::  align_pdf_to_asr(pdf_json, asr_json, *, window, step, ratio_thresh)
Returns the PDF utterances with `start`, `end`, and `pass_level`.
"""

from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Tuple

# trivial ASR fillers
_DROP = {"uh", "um", "erm"}


# -------------------------------------------------------------------
# helpers
def _norm(tok: str) -> str:
    tok = unicodedata.normalize("NFKD", tok).lower()
    tok = re.sub(r"[^\w\s']", "", tok)
    return "" if tok in _DROP else tok


def _words_stream(segments) -> List[Tuple[str, float, float]]:
    """Flatten ASR words → [(norm_word,start,end)]."""
    out = []
    for seg in segments:
        for w in seg["words"]:
            if w["start"] is None or w["end"] is None:
                continue
            out.append((_norm(w["word"]), w["start"], w["end"]))
    return out


# -------------------------------------------------------------------
# public entry point
def align_pdf_to_asr(
    pdf_json: str | Path,
    asr_json: str | Path,
    *,
    window: int = 120,          # primary pass window (words)
    step: int = 30,             # primary hop length
    ratio_thresh: float = 0.15, # primary acceptance ratio
) -> list[dict]:
    """
    Map every utterance in *pdf_json* onto the word-level ASR stream
    in *asr_json*.  Adds `start`, `end`, and `pass_level`.

    All utterances receive timestamps:
      primary      → high-confidence word match
      secondary    → sentence-text fuzzy match
      interpolated → linear fill between neighbours
    """
    pdf_utts = json.loads(Path(pdf_json).read_text())
    asr      = json.loads(Path(asr_json).read_text())["segments"]

    # ---- 1·PRIMARY WORD-LEVEL PASS ---------------------------------
    stream = _words_stream(asr)
    matched: list[dict] = []

    for utt in pdf_utts:
        # strip speaker label before scoring
        text = utt["text"].split(":", 1)[-1]
        words_norm = [_norm(t) for t in text.split() if _norm(t)]
        best = (0.0, -1)  # (ratio, stream_idx)

        for i in range(0, max(1, len(stream) - window), step):
            cand = [w for w, _, _ in stream[i : i + window]]
            r = SequenceMatcher(None, words_norm, cand).ratio()
            if r > best[0]:
                best = (r, i)

        if best[0] >= ratio_thresh:
            slice_ = stream[best[1] : best[1] + window]
            matched.append(
                {**utt,
                 "start": slice_[0][1],
                 "end":   slice_[-1][2],
                 "pass_level": "primary"}
            )
        else:
            matched.append({**utt, "start": None, "end": None})

    # ---- 2·SECONDARY SENTENCE-TEXT PASS ----------------------------
    empty = [i for i, m in enumerate(matched) if m["start"] is None]
    if empty:
        sent_texts = [seg["text"].lower() for seg in asr]
        win2, step2, ratio2 = 15, 5, 0.08

        for idx in empty:
            line = matched[idx]["text"].lower()
            best = (0.0, -1, -1)  # ratio, seg_start, seg_end
            for s in range(0, len(sent_texts) - win2, step2):
                chunk = " ".join(sent_texts[s : s + win2])
                r = SequenceMatcher(None, line, chunk).ratio()
                if r > best[0]:
                    best = (r, s, s + win2 - 1)
            if best[0] >= ratio2:
                seg_s, seg_e = best[1], best[2]
                matched[idx]["start"] = asr[seg_s]["start"]
                matched[idx]["end"]   = asr[seg_e]["end"]
                matched[idx]["pass_level"] = "secondary"

    # ---- 3·INTERPOLATION FALLBACK ----------------------------------
    prev_end = None
    for i, rec in enumerate(matched):
        if rec["start"] is not None:
            prev_end = rec["end"]
            continue
        nxt = next((m for m in matched[i + 1 :] if m["start"] is not None), None)
        if prev_end is not None and nxt is not None and nxt["start"] > prev_end:
            rec["start"], rec["end"] = prev_end, nxt["start"]
        else:
            # edge of file – assign arbitrary 2-second slot
            rec["start"] = prev_end or (nxt["start"] - 2.0 if nxt else 0.0)
            rec["end"]   = rec["start"] + 2.0
        rec["pass_level"] = "interpolated"

    return matched

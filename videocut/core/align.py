"""
Word-level aligner: map PDF utterances (no timestamps) to WhisperX JSON.

API
---
    align_pdf_to_asr(pdf_json, asr_json,
                     *, window=120, step=30, ratio_thresh=0.15) -> list[dict]

Returned list is a copy of the PDF utterances with `start` & `end`
(float seconds). Lines that fail to align keep start/end = None.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from difflib import SequenceMatcher
from typing import List, Tuple

# drop trivial ASR fillers
_DROP = {"uh", "um", "erm"}


def _norm(tok: str) -> str:
    """Lower-case, ASCII-fold, strip punctuation, drop fillers."""
    tok = unicodedata.normalize("NFKD", tok).lower()
    tok = re.sub(r"[^\w\s']", "", tok)
    return "" if tok in _DROP else tok


def _build_stream(segments) -> List[Tuple[str, float, float]]:
    """Flatten WhisperX segments \u2192 [(norm_word,start,end)]."""
    out: List[Tuple[str, float, float]] = []
    for seg in segments:
        for w in seg["words"]:
            if w["start"] is None or w["end"] is None:
                continue
            out.append((_norm(w["word"]), w["start"], w["end"]))
    return out


def align_pdf_to_asr(
    pdf_json: str | Path,
    asr_json: str | Path,
    *,
    window: int = 120,          # words per sliding window
    step: int = 30,             # hop length
    ratio_thresh: float = 0.15, # SequenceMatcher ratio to accept
) -> list[dict]:
    """Align utterances from *pdf_json* to word-level ASR in *asr_json*."""
    pdf_utts = json.loads(Path(pdf_json).read_text())
    stream   = _build_stream(
        json.loads(Path(asr_json).read_text())["segments"]
    )

    def _best_window(words_norm: list[str]) -> Tuple[float, int]:
        best = (0.0, -1)  # (ratio, index)
        limit = max(1, len(stream) - window + 1)
        for i in range(0, limit, step):
            cand = [w for w, _, _ in stream[i : i + window]]
            r = SequenceMatcher(None, words_norm, cand).ratio()
            if r > best[0]:
                best = (r, i)
        return best

    aligned = []
    for utt in pdf_utts:
        # strip speaker label before scoring
        text = utt["text"].split(":", 1)[-1]
        words_norm = [_norm(t) for t in text.split() if _norm(t)]
        ratio, idx = _best_window(words_norm)
        if ratio < ratio_thresh or idx == -1:
            aligned.append({**utt, "start": None, "end": None})
            continue
        slice_ = stream[idx : idx + window]
        aligned.append({**utt,
                        "start": slice_[0][1],
                        "end":   slice_[-1][2]})
    return aligned

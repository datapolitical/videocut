"""
Aligner: map PDF utterances (no timestamps) onto WhisperX word-level stream.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from difflib import SequenceMatcher

__all__ = ["align_pdf_to_asr"]

# --- Normalisation helpers -------------------------------------------------
_DROP = {"uh", "um", "erm"}

def _norm(token: str) -> str:
    tok = unicodedata.normalize("NFKD", token).lower()
    tok = re.sub(r"[^\w\s']", "", tok)
    return tok if tok not in _DROP else ""

# --- Core aligner ----------------------------------------------------------

def align_pdf_to_asr(
    pdf_path: Path,
    asr_path: Path,
    *,
    window: int = 80,
    step: int = 20,
    ratio_thresh: float = 0.55,
) -> list[dict]:
    """Return list of PDF utterances with start/end timings from ASR words."""
    pdf_utts = json.loads(pdf_path.read_text())
    asr = json.loads(asr_path.read_text())["segments"]

    # flatten ASR words -> [(norm_word, start, end)]
    stream: list[tuple[str, float, float]] = [
        (_norm(w["word"]), w["start"], w["end"])
        for seg in asr
        for w in seg.get("words", [])
        if w.get("start") is not None and w.get("end") is not None
    ]

    def _best_window(words_norm: list[str]):
        best = (0.0, None, None)
        for i in range(0, max(len(stream) - window, 1), step):
            cand = [w for w, _, _ in stream[i : i + window]]
            ratio = SequenceMatcher(None, words_norm, cand).ratio()
            if ratio > best[0]:
                best = (ratio, i, i + window)
        return best

    matched = []
    for utt in pdf_utts:
        words_norm = [_norm(t) for t in str(utt.get("text", "")).split() if _norm(t)]
        score, s, e = _best_window(words_norm)
        if score < ratio_thresh or s is None or e is None:
            matched.append({**utt, "start": None, "end": None})
            continue
        sl = stream[s:e]
        matched.append({**utt, "start": sl[0][1], "end": sl[-1][2]})
    return matched

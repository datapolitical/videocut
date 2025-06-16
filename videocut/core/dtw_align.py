"""
Band-limited DTW alignment between the entire text of
    pdf_transcript.txt  (accurate wording)
and
    *.srt               (accurate timing)

Every PDF word inherits the nearest SRT word-timestamp, then each PDF
sentence receives   start = first-word-time   and   end = last-word-time.

The DTW is constrained to a ±B tokens band (B≈100) so complexity is O(N·B).

Public entry
------------
    align_pdf_to_srt(pdf_txt, srt_path, band=100) -> list[dict]
"""

from __future__ import annotations
import re, unicodedata
from pathlib import Path
from typing import List, Tuple
import numpy as np
from fastdtw import fastdtw

# ---------------------------------------------------------------------
def _norm(tok: str) -> str:
    tok = unicodedata.normalize("NFKD", tok).lower()
    return re.sub(r"[^\w']", "", tok)

def _tokenize_lines(pdf_txt: str) -> Tuple[List[str], List[Tuple[int, int]], List[str]]:
    """Tokenize ``pdf_txt`` by line preserving exact text and bounds."""

    lines = [ln.strip() for ln in pdf_txt.splitlines()]
    norm_tokens: List[str] = []
    bounds: List[Tuple[int, int]] = []

    for line in lines:
        start_idx = len(norm_tokens)
        for tok in line.split():
            n = _norm(tok)
            if n:
                norm_tokens.append(n)
        end_idx = len(norm_tokens) - 1
        if start_idx > end_idx:
            bounds.append((None, None))
        else:
            bounds.append((start_idx, end_idx))

    return norm_tokens, bounds, lines

def _parse_srt(path: str | Path):
    pat = re.compile(
        r"\d+\s+(\d{2}:\d{2}:\d{2}),(\d{3})\s+-->\s+"
        r"(\d{2}:\d{2}:\d{2}),(\d{3})\s+(.+?)(?=\n\d+\n|\Z)", re.S)
    tokens, times = [], []
    for hh1, ms1, hh2, ms2, body in pat.findall(Path(path).read_text()):
        st = _hms_to_sec(hh1) + int(ms1) / 1000
        et = _hms_to_sec(hh2) + int(ms2) / 1000
        text = " ".join(body.strip().splitlines())
        toks = [_norm(t) for t in text.split() if _norm(t)]
        if not toks:
            continue
        # distribute tokens evenly across the caption duration while
        # ensuring strictly increasing timestamps
        step = max((et - st) / max(len(toks), 1), 0.001)
        cur = st
        for t in toks:
            tokens.append(t)
            times.append(cur)
            cur += step
    return tokens, np.array(times)

def _hms_to_sec(hms: str) -> float:
    h, m, s = map(int, hms.split(":"))
    return h*3600 + m*60 + s

# ---------------------------------------------------------------------
def _banded_dtw(src: List[str], ref: List[str], band: int = 100):
    """Approximate DTW alignment using ``fastdtw``.

    ``fastdtw`` runs in O(N) time and memory.  We treat token equality as
    distance 0 and mismatch as 1.  The ``band`` parameter becomes the
    ``radius`` used by ``fastdtw``.
    """

    # ``fastdtw`` expects numeric inputs, so map tokens to integers
    vocab = {t: i for i, t in enumerate({*src, *ref})}
    src_idx = [vocab[t] for t in src]
    ref_idx = [vocab[t] for t in ref]

    dist = lambda a, b: 0 if a == b else 1
    _dist, path = fastdtw(src_idx, ref_idx, radius=band, dist=dist)
    return path

# ---------------------------------------------------------------------
def align_pdf_to_srt(pdf_txt: str | Path,
                     srt_file: str | Path,
                     *,
                     band: int = 10) -> List[dict]:
    pdf_norm, pdf_bounds, pdf_lines = _tokenize_lines(Path(pdf_txt).read_text())
    srt_tokens, srt_times = _parse_srt(srt_file)

    mapping = _banded_dtw(pdf_norm, srt_tokens, band=band)
    # mapping[i] = (pdf_idx, srt_idx)

    pdf2time = {}
    for p_idx, s_idx in mapping:
        pdf2time[p_idx] = float(srt_times[s_idx])

    # propagate unmatched pdf tokens forward
    last_t = 0.0
    for i in range(len(pdf_norm)):
        if i in pdf2time:
            last_t = pdf2time[i]
        else:
            pdf2time[i] = last_t

    # line-level times
    out = []
    for line, (start_tok, end_tok) in zip(pdf_lines, pdf_bounds):
        if start_tok is None:
            st = et = None
        else:
            st = pdf2time[start_tok]
            et = pdf2time[end_tok]
        out.append(dict(text=line, start=st, end=et))

    # infer missing timestamps
    for i, rec in enumerate(out):
        if rec["start"] is not None:
            continue
        # previous known end
        j = i - 1
        while j >= 0 and out[j]["start"] is None:
            j -= 1
        prev_end = out[j]["end"] if j >= 0 else 0.0

        k = i + 1
        while k < len(out) and out[k]["start"] is None:
            k += 1
        next_start = out[k]["start"] if k < len(out) else prev_end

        rec["start"] = prev_end
        rec["end"] = next_start

    return out

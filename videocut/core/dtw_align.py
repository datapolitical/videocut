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

# ---------------------------------------------------------------------
def _norm(tok: str) -> str:
    tok = unicodedata.normalize("NFKD", tok).lower()
    return re.sub(r"[^\w']", "", tok)

def _tokenize_pdf(pdf_txt: str) -> Tuple[List[str], List[Tuple[int,int]]]:
    """Returns tokens and sentence-start indices."""
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', pdf_txt.strip())
    tokens, sent_bounds = [], []
    for sent in sentences:
        start_idx = len(tokens)
        toks = [_norm(t) for t in sent.split() if _norm(t)]
        tokens.extend(toks)
        sent_bounds.append((start_idx, len(tokens)-1))
    return tokens, sent_bounds

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
    """
    Banded DTW returning best path mapping indices of src→ref.
    cost = 0 if words equal else 1
    """
    n, m = len(src), len(ref)
    big = n + m + 1
    dp  = np.full((n+1, 2*band+1), big, np.int32)
    path = np.full((n+1, 2*band+1), -1, np.int16)   # 0=diag,1=up,2=left

    def idx(j,i):
        """column offset for ref-idx j at src-idx i"""
        return j - i + band

    dp[0, band] = 0
    for i in range(n + 1):
        for j in range(max(0, i - band), min(m, i + band) + 1):
            k = idx(j, i)
            if dp[i, k] == big:
                continue
            # diag
            if i < n and j < m:
                cost = 0 if src[i] == ref[j] else 1
                dk = idx(j + 1, i + 1)
                if 0 <= dk <= 2 * band and dp[i, k] + cost < dp[i + 1, dk]:
                    dp[i + 1, dk] = dp[i, k] + cost
                    path[i + 1, dk] = 0
            # up (src advance)
            if i < n:
                uk = idx(j, i + 1)
                if 0 <= uk <= 2 * band and dp[i, k] + 1 < dp[i + 1, uk]:
                    dp[i + 1, uk] = dp[i, k] + 1
                    path[i + 1, uk] = 1
            # left (ref advance)
            if j < m:
                lk = idx(j + 1, i)
                if 0 <= lk <= 2 * band and dp[i, k] + 1 < dp[i, lk]:
                    dp[i, lk] = dp[i, k] + 1
                    path[i, lk] = 2

    # back-trace
    j_range = range(max(0, n - band), min(m, n + band) + 1)
    i, j = n, min(j_range, key=lambda jj: dp[n, idx(jj, n)])
    align = []
    while i > 0 or j > 0:
        k = idx(j, i)
        move = path[i, k]
        if move == 0:
            align.append((i-1, j-1))
            i, j = i-1, j-1
        elif move == 1:
            i -= 1
        else:
            j -= 1
    return list(reversed(align))

# ---------------------------------------------------------------------
def align_pdf_to_srt(pdf_txt: str | Path,
                     srt_file: str | Path,
                     *,
                     band: int = 100) -> List[dict]:
    pdf_tokens, pdf_bounds  = _tokenize_pdf(Path(pdf_txt).read_text())
    srt_tokens, srt_times   = _parse_srt(srt_file)

    mapping = _banded_dtw(pdf_tokens, srt_tokens, band=band)
    # mapping[i] = (pdf_idx, srt_idx)

    pdf2time = {}
    for p_idx, s_idx in mapping:
        pdf2time[p_idx] = float(srt_times[s_idx])

    # propagate unmatched pdf tokens forward
    last_t = 0.0
    for i in range(len(pdf_tokens)):
        if i in pdf2time:
            last_t = pdf2time[i]
        else:
            pdf2time[i] = last_t

    # sentence-level times
    out = []
    tokens_seen = 0
    for start_tok, end_tok in pdf_bounds:
        st = pdf2time[start_tok]
        et = pdf2time[end_tok]
        sentence = " ".join(pdf_tokens[start_tok:end_tok+1])
        out.append(dict(text=sentence,
                        start=st,
                        end=et))
        tokens_seen = end_tok + 1
    return out

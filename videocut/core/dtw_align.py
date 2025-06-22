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
# Re-implement fast DTW style alignment without external deps.

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
def _reduce_by_half(seq: List[str]) -> List[str]:
    """Return every other element of ``seq`` used by FastDTW."""

    if len(seq) <= 1:
        return seq[:]
    return [seq[0]] + [seq[i] for i in range(2, len(seq), 2)]


def _expand_window(path: List[tuple[int, int]], m: int, n: int, radius: int) -> dict[int, tuple[int, int]]:
    """Expand a low-resolution path into a search window for higher resolution."""

    window: dict[int, list[int]] = {}
    for i, j in path:
        for di in range(-radius, radius + 1):
            for dj in range(-radius, radius + 1):
                ii = i * 2 + di
                jj = j * 2 + dj
                if 0 <= ii < m and 0 <= jj < n:
                    if ii not in window:
                        window[ii] = [jj, jj]
                    else:
                        window[ii][0] = min(window[ii][0], jj)
                        window[ii][1] = max(window[ii][1], jj)
    for i in range(m):
        if i not in window:
            window[i] = [0, n - 1]
    return {i: (rng[0], rng[1]) for i, rng in window.items()}


def _dtw_window(src: List[str], ref: List[str], window: dict[int, tuple[int, int]] | None, dist) -> tuple[float, list[tuple[int, int]]]:
    """Standard DTW with an optional constraint window."""

    m, n = len(src), len(ref)
    inf = float("inf")
    dp = np.full((m + 1, n + 1), inf)
    dp[0, 0] = 0.0

    if window is None:
        j_ranges = {i: (0, n - 1) for i in range(m)}
    else:
        j_ranges = window

    for i in range(1, m + 1):
        if i - 1 not in j_ranges:
            continue
        j_start, j_end = j_ranges[i - 1]
        j_start = max(0, j_start)
        j_end = min(n - 1, j_end)
        for j in range(j_start + 1, j_end + 2):
            cost = dist(src[i - 1], ref[j - 1])
            dp[i, j] = cost + min(dp[i - 1, j], dp[i, j - 1], dp[i - 1, j - 1])

    path = []
    i, j = m, n
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        step = int(np.argmin([dp[i - 1, j - 1], dp[i - 1, j], dp[i, j - 1]]))
        if step == 0:
            i -= 1
            j -= 1
        elif step == 1:
            i -= 1
        else:
            j -= 1

    while i > 0:
        i -= 1
        path.append((i, 0))
    while j > 0:
        j -= 1
        path.append((0, j))

    path.reverse()
    return float(dp[m, n]), path


def _fastdtw(src: List[str], ref: List[str], radius: int = 1) -> list[tuple[int, int]]:
    """Approximate DTW using the FastDTW algorithm."""

    dist = lambda a, b: 0 if a == b else 1

    def _recursive(a: List[str], b: List[str], rad: int) -> list[tuple[int, int]]:
        if len(a) <= rad + 2 or len(b) <= rad + 2:
            _, path = _dtw_window(a, b, None, dist)
            return path
        reduced_a = _reduce_by_half(a)
        reduced_b = _reduce_by_half(b)
        low_path = _recursive(reduced_a, reduced_b, rad)
        window = _expand_window(low_path, len(a), len(b), rad)
        _, path = _dtw_window(a, b, window, dist)
        return path

    return _recursive(src, ref, radius)

# ---------------------------------------------------------------------
def align_pdf_to_srt(pdf_txt: str | Path,
                     srt_file: str | Path,
                     *,
                     band: int = 10) -> List[dict]:
    pdf_norm, pdf_bounds, pdf_lines = _tokenize_lines(Path(pdf_txt).read_text())
    srt_tokens, srt_times = _parse_srt(srt_file)

    mapping = _fastdtw(pdf_norm, srt_tokens, radius=band)
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

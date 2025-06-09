"""Utilities for inserting segment markers into SRT files."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import chair


def _parse_time(ts: str) -> float:
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _format_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class _SrtEntry(dict):
    start: float
    end: float
    lines: list[str]


def _load_srt(path: Path) -> list[_SrtEntry]:
    entries: list[_SrtEntry] = []
    lines = path.read_text().splitlines()
    i = 0
    pending: list[str] = []
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        if lines[i].startswith("="):
            pending.append(lines[i].strip())
            i += 1
            continue
        number = lines[i].strip()
        i += 1
        if i >= len(lines):
            break
        ts_line = lines[i].strip()
        i += 1
        if "-->" not in ts_line:
            break
        start_str, end_str = [p.strip() for p in ts_line.split("-->")]
        start, end = _parse_time(start_str), _parse_time(end_str)
        text_lines: list[str] = pending
        pending = []
        while i < len(lines) and lines[i].strip():
            text_lines.append(lines[i])
            i += 1
        entries.append({"number": number, "start": start, "end": end, "lines": text_lines})
        while i < len(lines) and not lines[i].strip():
            i += 1
    return entries


def _find_entry(entries: list[_SrtEntry], t: float) -> int:
    for idx, e in enumerate(entries):
        if e["start"] <= t <= e["end"]:
            return idx
    for idx, e in enumerate(entries):
        if t < e["start"]:
            return idx
    return len(entries) - 1


_SPEAKER_RE = re.compile(r"^\[(SPEAKER_\d+)\]:\s*")


def annotate_srt(
    srt_file: str,
    seg_json: str = "segments_to_keep.json",
    name_map: str = "recognized_map.json",
    out_file: str = "processed.srt",
) -> None:
    """Insert ``=START-n=``/``=END-n=`` markers and map speaker labels."""
    entries = _load_srt(Path(srt_file))
    segs = json.loads(Path(seg_json).read_text())
    mapping = {}
    raw = {}
    if Path(name_map).exists():
        raw = json.loads(Path(name_map).read_text())
        mapping = {k: v.get("name", k) for k, v in raw.items() if isinstance(v, dict)}

    try:
        chair_id = chair.identify_chair_srt(srt_file)
    except Exception:
        chair_id = None
    if chair_id and chair_id not in mapping:
        if chair_id in raw and isinstance(raw[chair_id], dict):
            mapping[chair_id] = raw[chair_id].get("name", "Chair")
        else:
            mapping[chair_id] = "Chair"

    before: dict[int, list[str]] = {}
    after: dict[int, list[str]] = {}
    for i, seg in enumerate(sorted(segs, key=lambda s: s["start"]), 1):
        s_idx = _find_entry(entries, float(seg["start"]))
        e_idx = _find_entry(entries, float(seg["end"]))
        before.setdefault(s_idx, []).append(f"=START-{i}=")
        after.setdefault(e_idx, []).append(f"=END-{i}=")

    for e in entries:
        new_lines = []
        for line in e["lines"]:
            m = _SPEAKER_RE.match(line)
            if m:
                sp = m.group(1)
                name = mapping.get(sp, sp)
                line = _SPEAKER_RE.sub(f"{name}: ", line)
            new_lines.append(line)
        e["lines"] = new_lines

    out_lines: list[str] = []
    for idx, e in enumerate(entries):
        for m in before.get(idx, []):
            out_lines.append(m)
        out_lines.append(str(e["number"]))
        out_lines.append(f"{_format_time(e['start'])} --> {_format_time(e['end'])}")
        out_lines.extend(e["lines"])
        for m in after.get(idx, []):
            out_lines.append(m)
        out_lines.append("")

    Path(out_file).write_text("\n".join(out_lines))
    print(f"✅  wrote {out_file}")


_START_RE = re.compile(r"=START-(\d+)=")
_END_RE = re.compile(r"=END-(\d+)=")


def segments_from_srt(srt_file: str) -> list[dict]:
    """Return ``[{start, end}, ...]`` parsed from marker lines in *srt_file*."""
    entries = _load_srt(Path(srt_file))
    starts: dict[int, float] = {}
    segments: list[dict] = []
    for e in entries:
        for line in e["lines"]:
            m = _START_RE.match(line.strip())
            if m:
                starts[int(m.group(1))] = e["start"]
            m = _END_RE.match(line.strip())
            if m:
                idx = int(m.group(1))
                start = starts.pop(idx, e["start"])
                segments.append({"start": start, "end": e["end"]})
    return sorted(segments, key=lambda s: s["start"])


__all__ = ["annotate_srt", "segments_from_srt"]

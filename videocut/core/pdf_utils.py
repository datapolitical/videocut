import json
import re
from pathlib import Path
from typing import List, Set, Tuple, Dict

from pdfminer.high_level import extract_text
from .. import parse_pdf_text

__all__ = [
    "extract_speaker_names",
    "clean_recognized_map",
    "extract_transcript_lines",
    "extract_transcript_dialogue",
    "apply_pdf_transcript_json",
    "write_timestamped_transcript",
]


def extract_speaker_names(pdf_path: str) -> Set[str]:
    """Return a set of speaker names found in ``pdf_path``.

    The function looks for lines in the PDF that begin with an uppercase
    name followed by a colon and returns the names in title case.
    """
    text = extract_text(pdf_path)
    names: Set[str] = set()
    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Z'\- ]+):", line.strip())
        if m:
            name = re.sub(r"\s+", " ", m.group(1)).title()
            names.add(name)
    return names


def clean_recognized_map(mapping: dict, board_file: str | None = None, pdf_path: str | None = None) -> dict:
    """Return a copy of *mapping* with normalized speaker names.

    Names are matched against the board member list and optionally against
    names extracted from *pdf_path*.
    """
    from .nicholson import load_board_map, normalize_recognized_name
    from difflib import get_close_matches

    board_map = load_board_map(board_file)
    pdf_names = {n.lower(): n for n in extract_speaker_names(pdf_path)} if pdf_path else {}

    result = {}
    for spk, info in mapping.items():
        name = info.get("name", "")
        name = normalize_recognized_name(name, board_map)
        if pdf_names:
            match = get_close_matches(name.lower(), list(pdf_names.keys()), n=1, cutoff=0.8)
            if match:
                name = pdf_names[match[0]]
        alts = [normalize_recognized_name(a, board_map) for a in info.get("alternatives", []) if a]
        result[spk] = {"name": name, "alternatives": sorted(set(alts))}
    return result


def extract_transcript_lines(pdf_path: str) -> List[str]:
    """Return a list of transcript lines from *pdf_path*.

    This function delegates to :func:`videocut.parse_pdf_text.parse_pdf` to
    ensure multi-line statements spanning page breaks are preserved.
    """
    return parse_pdf_text.parse_pdf(pdf_path)


def extract_transcript_dialogue(pdf_path: str) -> List[Tuple[str, str]]:
    """Return ``(speaker, text)`` tuples parsed from ``pdf_path``."""
    dialogue: List[Tuple[str, str]] = []
    for line in parse_pdf_text.parse_pdf(pdf_path):
        if ":" not in line:
            continue
        speaker, text = line.split(":", 1)
        name = re.sub(r"\s+", " ", speaker).strip()
        dialogue.append((name, text.strip()))
    return dialogue


def apply_pdf_transcript_json(json_file: str, pdf_path: str, out_json: str | None = None) -> None:
    """Replace transcript lines and speakers in ``json_file`` using *pdf_path*."""
    data = json.loads(Path(json_file).read_text())
    dialog = extract_transcript_dialogue(pdf_path)
    segs = data.get("segments", [])
    for seg, (speaker, line) in zip(segs, dialog):
        seg["label"] = speaker
        seg["text"] = line
    if len(dialog) < len(segs):
        del segs[len(dialog):]
    Path(out_json or json_file).write_text(json.dumps(data, indent=2))
    print(f"✅  transcript text replaced → {out_json or json_file}")


_TS_RE = re.compile(r"^(\d+):(\d+):(\d+),(\d+)$")


def _parse_time(ts: str) -> float:
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _load_srt(path: Path) -> List[Dict[str, float | str]]:
    entries: List[Dict[str, float | str]] = []
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        if not lines[i].strip().isdigit():
            i += 1
            continue
        i += 1
        if i >= len(lines):
            break
        ts_line = lines[i].strip()
        i += 1
        if "-->" not in ts_line:
            continue
        start_str, end_str = [p.strip() for p in ts_line.split("-->")]
        start, end = _parse_time(start_str), _parse_time(end_str)
        text_lines = []
        while i < len(lines) and lines[i].strip():
            text_lines.append(lines[i].strip())
            i += 1
        entries.append({"start": start, "end": end, "text": " ".join(text_lines)})
        while i < len(lines) and not lines[i].strip():
            i += 1
    return entries


def write_timestamped_transcript(
    pdf_path: str,
    srt_path: str,
    out_txt: str | None = None,
    json_path: str | None = None,
) -> None:
    """Write ``out_txt`` with timestamps.

    If *json_path* is supplied and exists, timestamps and speaker names are
    taken directly from that JSON file instead of matching ``srt_path`` to the
    PDF text.  This provides a reliable fallback when the SRT and PDF texts do
    not align well.
    """
    if json_path and Path(json_path).exists():
        data = json.loads(Path(json_path).read_text())
        segs = data.get("segments", data)
        out_lines = []
        for seg in segs:
            start = float(seg.get("start", 0))
            end = float(seg.get("end", 0))
            speaker = seg.get("label") or seg.get("speaker", "")
            text = str(seg.get("text", "")).replace("\n", " ").strip()
            out_lines.append(f"[{start:.2f}-{end:.2f}] {speaker}: {text}")
        Path(out_txt or Path(pdf_path).with_suffix(".txt")).write_text(
            "\n".join(out_lines) + "\n"
        )
        print(
            f"✅  timestamped transcript → {out_txt or Path(pdf_path).with_suffix('.txt')}"
        )
        return

    dialogue = extract_transcript_dialogue(pdf_path)
    entries = _load_srt(Path(srt_path))
    out_lines: List[str] = []
    j = 0
    for speaker, text in dialogue:
        start, end = 0.0, 0.0
        collected = ""
        while j < len(entries):
            if not collected:
                start = entries[j]["start"]
            collected = (collected + " " + entries[j]["text"]).strip()
            end = entries[j]["end"]
            norm_target = re.sub(r"\s+", " ", text).lower()
            norm_collected = re.sub(r"\s+", " ", collected).lower()
            if norm_target in norm_collected or norm_collected in norm_target:
                j += 1
                break
            j += 1
        out_lines.append(f"[{start:.2f}-{end:.2f}] {speaker}: {text}")

    Path(out_txt or Path(pdf_path).with_suffix(".txt")).write_text(
        "\n".join(out_lines) + "\n"
    )
    print(
        f"✅  timestamped transcript → {out_txt or Path(pdf_path).with_suffix('.txt')}"
    )

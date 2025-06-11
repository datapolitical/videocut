import json
import re
from pathlib import Path
from typing import List, Set, Tuple, Dict

from pdfminer.high_level import extract_text

__all__ = [
    "extract_speaker_names",
    "clean_recognized_map",
    "extract_transcript_lines",
    "extract_transcript_dialogue",
    "apply_pdf_transcript_json",
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

    Each returned line is normalized to single spaces and stripped of
    leading/trailing whitespace.
    """
    text = extract_text(pdf_path)
    lines: List[str] = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line.strip())
        if not line:
            continue
        if re.match(r"^[A-Z][A-Z'\- ]+:", line):
            lines.append(line)
    return lines


def extract_transcript_dialogue(pdf_path: str) -> List[Tuple[str, str]]:
    """Return ``(speaker, text)`` tuples parsed from ``pdf_path``."""
    dialogue: List[Tuple[str, str]] = []
    for line in extract_transcript_lines(pdf_path):
        m = re.match(r"^([A-Z][A-Z'\- ]+):\s*(.*)", line)
        if m:
            name = re.sub(r"\s+", " ", m.group(1)).title()
            dialogue.append((name, m.group(2)))
    return dialogue


def apply_pdf_transcript_json(json_file: str, pdf_path: str, out_json: str | None = None) -> None:
    """Replace transcript lines and speakers in ``json_file`` using *pdf_path*."""
    data = json.loads(Path(json_file).read_text())
    dialog = extract_transcript_dialogue(pdf_path)
    segs = data.get("segments", [])
    for seg, (speaker, line) in zip(segs, dialog):
        seg["speaker"] = speaker
        seg["text"] = line
    Path(out_json or json_file).write_text(json.dumps(data, indent=2))
    print(f"✅  transcript text replaced → {out_json or json_file}")

import json
import re
from pathlib import Path
from typing import Dict

# Regex to detect a roll call announcement
# Regex to detect a roll call announcement
_ROLL_RE = re.compile(
    r"roll\s?call|call(?:ing)?(?:\s+the)?\s+roll|take(?:\s+the)?\s+roll",
    re.IGNORECASE,
)
# Additional chair phrases that can appear later in the meeting
_MOTION_RE = re.compile(
    r"(?:do|can|may)\s+i\s+have\s+a\s+motion|entertain\s+a\s+motion",
    re.IGNORECASE,
)
_MOVE_RE = re.compile(r"moving on", re.IGNORECASE)
_CHAIR_REPORT_RE = re.compile(r"chair['’]?s report", re.IGNORECASE)
_ANY_OTHER_RE = re.compile(r"any other (?:directors? )?comments|any other matters", re.IGNORECASE)
# Regex to extract names announced during roll call
_NAME_RE = re.compile(
    r"(?:director|secretary|treasurer|chair(?:man)?|vice chair)\s+(?P<name>[A-Za-z]+(?: [A-Za-z]+)*)",
    re.IGNORECASE,
)
_PRESENT_RE = re.compile(r"\b(present|here)\b", re.IGNORECASE)

_SPEAKER_RE = re.compile(r"\[(SPEAKER_\d+)\]")

__all__ = ["identify_chair", "parse_roll_call", "identify_chair_srt"]

_HEURISTICS = [
    (_ROLL_RE, 5),
    (_MOTION_RE, 3),
    (_MOVE_RE, 1),
    (_CHAIR_REPORT_RE, 2),
    (_ANY_OTHER_RE, 1),
]


def identify_chair(diarized_json: str) -> str:
    """Return the diarized speaker ID most likely acting as chair."""
    data = json.loads(Path(diarized_json).read_text())
    segments = data.get("segments", [])
    scores: Dict[str, int] = {}
    for seg in segments:
        text = seg.get("text", "")
        speaker = seg.get("speaker")
        for pat, weight in _HEURISTICS:
            if pat.search(text):
                scores[speaker] = scores.get(speaker, 0) + weight
    if scores:
        return max(scores.items(), key=lambda kv: kv[1])[0]
    # Fallback: look for a name/present pair to infer the chair
    for i, seg in enumerate(segments):
        if _NAME_RE.search(seg.get("text", "")):
            j = i + 1
            while j < len(segments) and segments[j].get("speaker") == seg.get("speaker"):
                j += 1
            if j < len(segments) and _PRESENT_RE.search(segments[j].get("text", "")):
                return seg.get("speaker")
    raise RuntimeError("No roll call detected – unable to identify chair")


def parse_roll_call(diarized_json: str) -> Dict[str, str]:
    """Return mapping of names to diarized speaker IDs from the roll call."""
    data = json.loads(Path(diarized_json).read_text())
    segments = data.get("segments", [])
    votes: Dict[str, str] = {}
    chair_id = None
    i = 0
    # locate roll call or infer from first name/present pair
    while i < len(segments):
        text = segments[i].get("text", "")
        if _ROLL_RE.search(text) or _MOTION_RE.search(text):
            chair_id = segments[i].get("speaker")
            i += 1
            break
        if _NAME_RE.search(text):
            j = i + 1
            while j < len(segments) and segments[j].get("speaker") == segments[i].get("speaker"):
                j += 1
            if j < len(segments) and _PRESENT_RE.search(segments[j].get("text", "")):
                chair_id = segments[i].get("speaker")
                break
        i += 1
    if chair_id is None:
        raise RuntimeError("No roll call found")
    # parse name / response pairs
    while i < len(segments):
        text = segments[i].get("text", "")
        m = _NAME_RE.search(text)
        if m:
            name = m.group("name").title()
            j = i + 1
            # skip chair's own segments
            while j < len(segments) and segments[j].get("speaker") == chair_id:
                j += 1
            if j < len(segments) and _PRESENT_RE.search(segments[j].get("text", "")):
                votes[name] = segments[j].get("speaker")
            i = j
            continue
        elif _ROLL_RE.search(text):
            break
        i += 1
    return votes


def identify_chair_srt(srt_file: str) -> str:
    """Return the speaker tag that calls the roll in an SRT file."""
    for line in Path(srt_file).read_text().splitlines():
        if _ROLL_RE.search(line) or _MOTION_RE.search(line):
            m = _SPEAKER_RE.search(line)
            if m:
                return m.group(1)
    raise RuntimeError("No roll call detected – unable to identify chair")

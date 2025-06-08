import json
import re
from pathlib import Path
from typing import Dict

# Regex to detect a roll call announcement
_ROLL_RE = re.compile(r"roll call|call the roll", re.IGNORECASE)
# Regex to extract names announced during roll call
_NAME_RE = re.compile(
    r"(?:director|secretary|treasurer|chair(?:man)?|vice chair)\s+(?P<name>[A-Za-z]+(?: [A-Za-z]+)*)",
    re.IGNORECASE,
)
_PRESENT_RE = re.compile(r"\b(present|here)\b", re.IGNORECASE)

__all__ = ["identify_chair", "parse_roll_call"]

def identify_chair(diarized_json: str) -> str:
    """Return the diarized speaker ID who calls the roll."""
    data = json.loads(Path(diarized_json).read_text())
    for seg in data.get("segments", []):
        if _ROLL_RE.search(seg.get("text", "")):
            return seg.get("speaker")
    raise RuntimeError("No roll call detected – unable to identify chair")


def parse_roll_call(diarized_json: str) -> Dict[str, str]:
    """Return mapping of names to diarized speaker IDs from the roll call."""
    data = json.loads(Path(diarized_json).read_text())
    segments = data.get("segments", [])
    votes: Dict[str, str] = {}
    chair_id = None
    i = 0
    # locate roll call
    while i < len(segments):
        if _ROLL_RE.search(segments[i].get("text", "")):
            chair_id = segments[i].get("speaker")
            i += 1
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

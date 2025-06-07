"""Nicholson segmentation helpers."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

# Key phrases for speaker identification
_NICHOLSON_KEY_PHRASES = {
    "secretary nicholson",
    "director nicholson",
    "nicholson, for the record",
}

_END_PATTERNS = [r"\bthank you\b", r"\bnext item\b", r"\bmove on\b", r"\bdirector\b", r"\bchair\b"]
_END_RE = re.compile("|".join(_END_PATTERNS), re.IGNORECASE)
_TS_RE = re.compile(r"^\s*\[(?P<start>\d+\.?\d*)[–-](?P<end>\d+\.?\d*)\]\s*(?P<rest>.*)")
_ROLL_RE = re.compile(r"roll call", re.IGNORECASE)
_NICH_ITEM_RE = re.compile(r"nicholson", re.IGNORECASE)

TRAIL_SEC = 30
PRE_SEC = 5


def map_nicholson_speaker(diarized_json: str) -> str:
    """Return the WhisperX speaker label matching Nicholson."""
    data = json.loads(Path(diarized_json).read_text())
    counts: Dict[str, int] = {}
    for seg in data["segments"]:
        spk = seg.get("speaker")
        if not spk:
            continue
        text_l = seg["text"].lower()
        if any(p in text_l for p in _NICHOLSON_KEY_PHRASES):
            counts[spk] = counts.get(spk, 0) + 1
    if not counts:
        raise RuntimeError("Nicholson phrases not found – update key phrases or re-check diarization.")
    best = max(counts, key=counts.get)
    print(f"🔍  Identified Secretary Nicholson as {best} (matches={counts[best]})")
    return best


def map_speaker_by_phrases(diarized_json: str, phrase_map: Dict[str, List[str]]) -> Dict[str, str]:
    """Return WhisperX speaker IDs for each name in *phrase_map*.

    The *phrase_map* argument maps a display name to one or more key phrases
    uniquely spoken by that person. Each speaker ID is chosen by counting which
    diarized speaker label says the most of that person's phrases, following the
    same strategy as :func:`map_nicholson_speaker`.
    """

    data = json.loads(Path(diarized_json).read_text())
    segments = data["segments"]
    result: Dict[str, str] = {}

    for name, phrases in phrase_map.items():
        counts: Dict[str, int] = {}
        phr_lower = [p.lower() for p in phrases]
        for seg in segments:
            spk = seg.get("speaker")
            if not spk:
                continue
            text_l = seg.get("text", "").lower()
            if any(p in text_l for p in phr_lower):
                counts[spk] = counts.get(spk, 0) + 1
        if not counts:
            raise RuntimeError(
                f"Phrases for {name} not found – update key phrases or re-check diarization."
            )
        best = max(counts, key=counts.get)
        print(f"🔍  Identified {name} as {best} (matches={counts[best]})")
        result[name] = best

    return result


def map_recognized_speakers(
    diarized_json: str,
    chair_id: str,
    recognition_map: Dict[str, List[str]],
) -> Dict[str, str]:
    """Return speaker IDs for names the chair recognizes.

    Each entry in *recognition_map* maps a person's name to phrases that appear
    in the chair's dialog when they are recognized. The diarized speaker who
    talks next after such a phrase is counted as that person, and the speaker ID
    with the most counts for each name is returned.
    """

    data = json.loads(Path(diarized_json).read_text())
    segments = data["segments"]
    counts: Dict[str, Dict[str, int]] = {name: {} for name in recognition_map}

    for i, seg in enumerate(segments):
        if seg.get("speaker") != chair_id:
            continue
        text_l = seg.get("text", "").lower()
        for name, phrases in recognition_map.items():
            if any(p.lower() in text_l for p in phrases):
                j = i + 1
                while j < len(segments) and segments[j].get("speaker") == chair_id:
                    j += 1
                if j < len(segments):
                    spk = segments[j].get("speaker")
                    sub = counts[name]
                    sub[spk] = sub.get(spk, 0) + 1
                break

    result: Dict[str, str] = {}
    for name, spk_counts in counts.items():
        if not spk_counts:
            raise RuntimeError(
                f"Recognition phrases for {name} not found – update key phrases or re-check diarization."
            )
        best = max(spk_counts, key=spk_counts.get)
        print(f"🔍  Recognized {name} as {best} (matches={spk_counts[best]})")
        result[name] = best

    return result


_AUTO_RECOG_RE = re.compile(
    r"(?i:(?:director|secretary|chair|treasurer|mr|ms|mrs))\.?\s*(?P<name>[a-zA-Z]+(?: [a-zA-Z]+)*)\s+(?:you(?:'re| are)|is) recognized",
)

# "You're recognized" without a name
_RECOG_SIMPLE_RE = re.compile(r"you(?:'re| are) recognized", re.IGNORECASE)

# Name mentioned before a recognition cue
_NAME_BEFORE_RE = re.compile(
    r"(?i:(?:director|secretary|chair|treasurer|mr|ms|mrs))\.?\s+(?P<name>[A-Za-z]+(?: [A-Za-z]+)?)\b",
)

# Chair mentions without a recognition phrase
_NAME_MENTION_RE = _NAME_BEFORE_RE


def map_recognized_auto(diarized_json: str) -> Dict[str, str]:
    """Infer recognized speakers directly from diarized text.

    The function searches for phrases such as "director Doe you're recognized".
    The next speaker after the phrase is counted as the recognized person. The
    most frequent speaker ID for each detected name is returned.
    """

    data = json.loads(Path(diarized_json).read_text())
    segments = data["segments"]

    chair_counts: Dict[str, int] = {}
    for seg in segments:
        spk = seg.get("speaker")
        if not spk:
            continue
        text = seg.get("text", "")
        if _RECOG_SIMPLE_RE.search(text) or _NAME_MENTION_RE.search(text):
            chair_counts[spk] = chair_counts.get(spk, 0) + 1

    if not chair_counts:
        raise RuntimeError("Unable to detect chair from transcript")

    chair_id = max(chair_counts, key=chair_counts.get)

    counts: Dict[str, Dict[str, int]] = {}

    for i, seg in enumerate(segments):
        if seg.get("speaker") != chair_id:
            continue

        text = seg.get("text", "")
        name = None

        m = _AUTO_RECOG_RE.search(text)
        if m:
            name = m.group("name").title()
        elif _RECOG_SIMPLE_RE.search(text):
            back_text = []
            j = i - 1
            while j >= 0 and len(back_text) < 3 and segments[j].get("speaker") == chair_id:
                back_text.insert(0, segments[j].get("text", ""))
                j -= 1
            joined = " ".join(back_text)
            matches = list(_NAME_MENTION_RE.finditer(joined))
            if matches:
                raw = matches[-1].group("name")
                parts = raw.split()
                if (
                    raw[0].isalpha()
                    and len(raw) > 1
                    and parts[0].lower() not in {"on", "at", "any", "the"}
                    and not (
                        len(parts) > 1 and parts[1].lower() in {"and", "as", "is", "would", "the", "or"}
                    )
                ):
                    if len(parts) == 2 and not parts[1][0].isupper():
                        pass
                    else:
                        name = raw.title()
        else:
            m2 = _NAME_MENTION_RE.search(text)
            if m2:
                raw = m2.group("name")
                parts = raw.split()
                if (
                    raw[0].isalpha()
                    and len(raw) > 1
                    and parts[0].lower() not in {"on", "at", "any", "the"}
                    and not (
                        len(parts) > 1 and parts[1].lower() in {"and", "as", "is", "would", "the", "or"}
                    )
                ):
                    if len(parts) == 2 and not parts[1][0].isupper():
                        pass
                    else:
                        name = raw.title()

        if not name:
            continue

        j = i + 1
        while j < len(segments) and segments[j].get("speaker") == chair_id:
            j += 1
        if j < len(segments):
            spk = segments[j].get("speaker")
            if spk:
                sub = counts.setdefault(name, {})
                sub[spk] = sub.get(spk, 0) + 1

    if not counts:
        raise RuntimeError("No recognition cues found – unable to map speakers.")

    result: Dict[str, str] = {}
    for name, spk_counts in counts.items():
        best = max(spk_counts, key=spk_counts.get)
        print(f"🔍  Recognized {name} as {best} (matches={spk_counts[best]})")
        result[name] = best

    return result


def add_speaker_labels(
    diarized_json: str,
    id_map: Dict[str, str],
    out_json: str = "labeled.json",
) -> None:
    """Write a copy of *diarized_json* with name labels added.

    The *id_map* argument maps display names to WhisperX speaker IDs. Each
    segment whose ``speaker`` matches an ID gets a ``label`` field with the
    corresponding name.
    """

    data = json.loads(Path(diarized_json).read_text())
    segments = data["segments"]
    inv = {v: k for k, v in id_map.items()}
    for seg in segments:
        spk = seg.get("speaker")
        name = inv.get(spk)
        if name:
            seg["label"] = name
    Path(out_json).write_text(json.dumps(data, indent=2))
    print(f"✅  labels added → {out_json}")


def auto_segments_for_speaker(diarized_json: str, speaker_id: str, out_json: str = "segments_to_keep.json") -> None:
    """Dump every segment spoken by *speaker_id* into JSON."""
    data = json.loads(Path(diarized_json).read_text())
    segs = [{"start": seg["start"], "end": seg["end"]} for seg in data["segments"] if seg.get("speaker") == speaker_id]
    Path(out_json).write_text(json.dumps(segs, indent=2))
    print(f"✅  {len(segs)} Nicholson segment(s) → {out_json}")


def auto_mark_nicholson(diarized_json: str, out_json: str = "segments_to_keep.json") -> None:
    """End-to-end helper to create JSON for Nicholson clips."""
    segment_nicholson(diarized_json, out_json)


def load_markup(path: Path) -> List[dict]:
    lines = []
    if not path.exists():
        return lines
    for line in path.read_text().splitlines():
        m = _TS_RE.match(line)
        if not m:
            continue
        lines.append({"start": float(m.group("start")), "end": float(m.group("end")), "line": line})
    return lines


def collect_pre(segs: List[dict], start: float) -> List[str]:
    window = start - PRE_SEC
    return [s["line"] for s in segs if s["end"] <= start and s["end"] >= window]


def collect_post(segs: List[dict], end: float, next_start: float | None = None) -> List[str]:
    window = end + TRAIL_SEC
    out = []
    for l in segs:
        if l["start"] < end:
            continue
        if next_start is not None and l["start"] >= next_start:
            break
        if l["start"] > window:
            break
        out.append(l["line"])
    return out


def trim_segment(start: float, end: float, markup: List[dict]) -> tuple[float, List[str]]:
    lines = [l for l in markup if l["start"] < end and l["end"] > start]
    for l in lines:
        if _ROLL_RE.search(l["line"]):
            prev = [p for p in markup if p["end"] <= l["start"] and p["end"] >= l["start"] - 60]
            if not any(_NICH_ITEM_RE.search(p["line"]) for p in prev):
                end = min(end, l["start"])
                break
    trimmed = [l["line"] for l in markup if l["start"] < end and l["end"] > start]
    return end, trimmed


def should_end(text: str) -> bool:
    return bool(_END_RE.search(text))


def find_nicholson_speaker(segments: List[dict]) -> str | None:
    cues = [
        "i have secretary nicholson",
        "thank you very much, secretary nicholson",
        "nicholson, do i have",
    ]
    for i, seg in enumerate(segments):
        txt = seg.get("text", "").lower()
        if any(c in txt for c in cues):
            j = i + 1
            while j < len(segments) and segments[j]["speaker"] == seg["speaker"]:
                j += 1
            if j < len(segments):
                return segments[j]["speaker"]
    candidate = None
    for i, seg in enumerate(segments):
        txt = seg.get("text", "").lower()
        if "nicholson" in txt:
            j = i + 1
            while j < len(segments) and segments[j]["speaker"] == seg["speaker"]:
                j += 1
            if j < len(segments):
                candidate = segments[j]["speaker"]
    return candidate


def segment_nicholson(diarized_json: str, out_json: str = "segments_to_keep.json") -> None:
    in_path = Path(diarized_json)
    out_path = Path(out_json)
    markup_path = in_path.with_name("markup_guide.txt")

    data = json.loads(in_path.read_text())
    segs = data["segments"]
    markup_lines = load_markup(markup_path)

    nicholson_id = find_nicholson_speaker(segs)
    if nicholson_id is None:
        nicholson_id = map_nicholson_speaker(str(in_path))

    print(f"🔍  Secretary Nicholson identified as {nicholson_id}")

    results = []
    n_idx = [i for i, seg in enumerate(segs) if seg.get("speaker") == nicholson_id]
    if not n_idx:
        out_path.write_text("[]")
        print("❌  No Nicholson segments found")
        return

    groups = []
    start_idx = n_idx[0]
    last_idx = n_idx[0]
    for idx in n_idx[1:]:
        prev_end = float(segs[last_idx]["end"])
        cur_start = float(segs[idx]["start"])
        if cur_start - prev_end >= 120:
            groups.append((start_idx, last_idx))
            start_idx = idx
        last_idx = idx
    groups.append((start_idx, last_idx))

    for start_idx, last_idx in groups:
        start_time = float(segs[start_idx]["start"])
        end_time = float(segs[last_idx]["end"])

        j = last_idx + 1
        while j < len(segs):
            seg = segs[j]
            if seg.get("speaker") == nicholson_id:
                break
            if float(seg["start"]) - end_time >= 120 and should_end(seg.get("text", "")):
                end_time = float(seg["end"])
                break
            end_time = float(seg["end"])
            j += 1
        if j < len(segs):
            next_start = float(segs[j]["start"])
            end_time = min(end_time + TRAIL_SEC, next_start)
        else:
            next_start = None
            end_time = end_time + TRAIL_SEC

        end_time, segment_lines = trim_segment(start_time, end_time, markup_lines)
        pre_lines = collect_pre(markup_lines, start_time)
        post_lines = collect_post(markup_lines, end_time, next_start)

        results.append({
            "start": round(start_time, 2),
            "end": round(end_time, 2),
            "text": segment_lines,
            "pre": pre_lines,
            "post": post_lines,
        })

    out_path.write_text(json.dumps(results, indent=2))
    print(f"✅  {len(results)} segments → {out_path}")

__all__ = [
    "map_nicholson_speaker",
    "map_speaker_by_phrases",
    "map_recognized_speakers",
    "map_recognized_auto",
    "add_speaker_labels",
    "auto_segments_for_speaker",
    "auto_mark_nicholson",
    "find_nicholson_speaker",
    "segment_nicholson",
]

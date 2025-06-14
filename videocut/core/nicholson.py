"""Nicholson segmentation helpers."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
from functools import reduce
from difflib import get_close_matches
import csv

import pdfminer.high_level

_norm_re = re.compile(r"\s+")

def _normalize(text: str) -> str:
    return _norm_re.sub(" ", text.strip()).lower()


def _parse_pdf_order(pdf_path: str):
    text = pdfminer.high_level.extract_text(pdf_path)
    raw_lines = [l.strip() for l in text.splitlines() if l.strip()]
    pattern = re.compile(r"^([A-Z][A-Z ']+):\s*(.*)")
    lines = []
    current_speaker = None
    for line in raw_lines:
        m = pattern.match(line)
        if m:
            current_speaker = m.group(1).title()
            text_line = m.group(2).strip()
            lines.append((current_speaker, text_line))
        else:
            if current_speaker is not None:
                spk, prev = lines[-1]
                lines[-1] = (spk, prev + ' ' + line.strip())
    return lines


def _parse_tsv(tsv_path: str):
    entries = []
    with open(tsv_path) as f:
        next(f)
        for line in f:
            parts = line.rstrip("\n").split("\t", 2)
            if len(parts) < 3:
                # Skip malformed rows
                continue
            start, end, text = parts
            entries.append({
                "start": float(start) / 1000.0,
                "end": float(end) / 1000.0,
                "text": text.strip(),
            })
    return entries


def _align_transcript(pdf_lines, tsv_entries):
    j = 0
    for entry in tsv_entries:
        target = _normalize(entry["text"])
        for k in range(j, len(pdf_lines)):
            spk, txt = pdf_lines[k]
            if target in _normalize(txt):
                entry["speaker"] = spk
                j = k
                break
        else:
            entry["speaker"] = ""
    return tsv_entries


def _build_segments(entries, gap: int | None = None):
    if gap is None:
        gap = END_GAP_SEC
    segments = []
    active = False
    start_time = None
    last_nich = None
    last_time = None
    end_time = None
    for i, ent in enumerate(entries):
        text_l = ent["text"].lower()
        spk_l = ent.get("speaker", "").lower()
        is_nich = "nicholson" in text_l or spk_l.startswith("chris nicholson")

        if is_nich:
            if not active:
                start_time = max(0.0, ent["start"] - 5)
                active = True
            last_nich = ent["end"]
            end_time = ent["end"]
            last_time = ent["end"]
        elif active:
            if _recognizes_other(text_l):
                next_start = (
                    entries[i + 1]["start"] if i + 1 < len(entries) else ent["end"]
                )
                segments.append({"start": start_time, "end": next_start})
                active = False
                start_time = None
                last_nich = None
                end_time = None
                last_time = None
                continue
            if last_time is not None and ent["start"] - last_time <= gap:
                end_time = ent["end"]
                last_time = ent["end"]
            else:
                segments.append({"start": start_time, "end": (last_nich or end_time) + 10})
                active = False
                start_time = None
                last_nich = None
                end_time = None
                last_time = None
                continue

    if active:
        segments.append({"start": start_time, "end": (last_nich or end_time) + 10})

    merged = []
    for seg in segments:
        if merged and seg["start"] - merged[-1]["end"] <= 15:
            merged[-1]["end"] = seg["end"]
        else:
            merged.append(seg)
    return merged

from . import chair

# Key phrases for speaker identification
_NICHOLSON_KEY_PHRASES = {
    "secretary nicholson",
    "director nicholson",
    "nicholson, for the record",
}

_END_PATTERNS = [r"\bthank you\b", r"\bnext item\b", r"\bmove on\b", r"\bdirector\b", r"\bchair\b", r"\bthat concludes\b", r"\bno further\b"]
_END_RE = re.compile("|".join(_END_PATTERNS), re.IGNORECASE)

_START_SIGNALS = {
    r"\bsecretary nicholson\b": 0.8,
    r"\bdirector nicholson\b": 0.8,
    r"\bi have secretary nicholson\b": 0.8,
    r"\bnicholson, do i have\b": 0.8,
}

_END_SIGNALS = {
    r"\bthank you\b": 0.6,
    r"\bnext item\b": 0.8,
    r"\bmove on\b": 0.7,
    r"\bdirector\b": 0.5,
    r"\bchair\b": 0.5,
    r"\bthat concludes\b": 0.8,
    r"\bno further\b": 0.7,
}


def _recognizes_other(text: str) -> bool:
    """Return True if *text* cues recognition of someone other than Nicholson."""
    text_l = text.lower()
    if "nicholson" in text_l:
        return False
    if _AUTO_RECOG_RE.search(text_l) or _YIELD_RE.search(text_l) or _NAME_ONLY_RE.match(text_l):
        return True
    if _NAME_BEFORE_RE.search(text_l) and len(text_l.split()) <= 4:
        return True
    return False

START_THRESHOLD = 0.8
END_THRESHOLD = 0.7
_TS_RE = re.compile(r"^\s*\[(?P<start>\d+\.?\d*)[–-](?P<end>\d+\.?\d*)\]\s*(?P<rest>.*)")
_ROLL_RE = re.compile(r"roll call", re.IGNORECASE)
_NICH_ITEM_RE = re.compile(r"nicholson", re.IGNORECASE)

TRAIL_SEC = 30
PRE_SEC = 5
MERGE_GAP_SEC = 120
END_GAP_SEC = 30

BOARD_FILE = Path(__file__).resolve().parents[1] / "board_members.txt"


def load_board_names(path: str | None = None) -> set[str]:
    """Return a set of official board or staff names in lowercase."""
    fp = Path(path) if path else BOARD_FILE
    if not fp.exists():
        return set()
    return {ln.strip().lower() for ln in fp.read_text().splitlines() if ln.strip()}


def load_board_map(path: str | None = None) -> Dict[str, str]:
    """Return a mapping of lowercase names to their canonical form."""
    fp = Path(path) if path else BOARD_FILE
    if not fp.exists():
        return {}
    mapping = {}
    for line in fp.read_text().splitlines():
        name = line.strip()
        if name:
            mapping[name.lower()] = name
    return mapping


def _is_board_member(name: str, board: set[str]) -> bool:
    if not name:
        return False
    return bool(get_close_matches(name.lower(), list(board), n=1, cutoff=0.75))


def normalize_recognized_name(name: str, board_map: Dict[str, str]) -> str:
    """Return *name* corrected to the closest official name if similar."""
    if not name:
        return name
    lname = name.lower()
    if lname in board_map:
        return board_map[lname]
    match = get_close_matches(lname, list(board_map.keys()), n=1, cutoff=0.65)
    if match:
        return board_map[match[0]]
    # attempt to match just on last name
    last = lname.split()[-1]
    last_map = {n.split()[-1].lower(): n for n in board_map.values()}
    if last in last_map:
        return last_map[last]
    return name


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


# common pattern for a person name (1 or 2 words, allow apostrophes/hyphens)
_NAME_TOKEN = r"[A-Za-z'’-]+"

_AUTO_RECOG_RE = re.compile(
    rf"(?:director|secretary|chair|treasurer|mr|ms|mrs)\.?\s*(?P<name>{_NAME_TOKEN}(?: {_NAME_TOKEN})?)\s+(?:you(?:'re| are)|is) recognized",
    re.IGNORECASE,
)

# "You're recognized" without a name
_RECOG_SIMPLE_RE = re.compile(r"you(?:'re| are) recognized", re.IGNORECASE)

# Name mentioned before a recognition cue
_NAME_BEFORE_RE = re.compile(
    rf"(?:director|secretary|chair|treasurer|mr|ms|mrs)\.?\s+(?P<name>{_NAME_TOKEN}(?: {_NAME_TOKEN})?)\b",
    re.IGNORECASE,
)

# Short statement that is just a titled name
_NAME_ONLY_RE = re.compile(
    rf"^(?:director|secretary|chair|treasurer|mr|ms|mrs|dr)\.?\s+(?P<name>{_NAME_TOKEN}(?: {_NAME_TOKEN})?)[.,?]*$",
    re.IGNORECASE,
)

# Yield or call on someone to speak
_YIELD_RE = re.compile(
    rf"(?:yield|offer) (?:the )?floor to (?:director|secretary|chair|treasurer|mr|ms|mrs|dr)\.?\s*(?P<name>{_NAME_TOKEN}(?: {_NAME_TOKEN})?)"
    rf"|call(?:ing)? on (?:director|secretary|chair|treasurer|mr|ms|mrs|dr)\.?\s*(?P<name2>{_NAME_TOKEN}(?: {_NAME_TOKEN})?)",
    re.IGNORECASE,
)


def map_recognized_auto(diarized_json: str) -> Dict[str, dict]:
    """Infer recognized speakers directly from diarized text.

    The function first determines the chair using :func:`chair.identify_chair`
    and parses the roll call. It then scans the chair's dialog for phrases such
    as "director Doe you're recognized". The next speaker after the phrase is
    counted as that person. Results map each diarized speaker ID to a
    ``{"name": str, "alternatives": list}`` structure containing the most likely
    name and any alternative names detected for that speaker. Names from the roll
    call are merged into the final mapping.
    """

    data = json.loads(Path(diarized_json).read_text())
    segments = data["segments"]

    chair_id = chair.identify_chair(diarized_json)
    roll_map = chair.parse_roll_call(diarized_json)
    board_map = load_board_map()

    counts: Dict[str, Dict[str, int]] = {}

    for i, seg in enumerate(segments):
        if seg.get("speaker") != chair_id:
            continue
        text = seg.get("text", "")
        speaker = seg.get("speaker")
        text_l = text.lower()
        m = _AUTO_RECOG_RE.search(text_l)
        name = None
        if m:
            name = m.group("name").title()
            name = normalize_recognized_name(name, board_map)
        elif _RECOG_SIMPLE_RE.search(text_l):
            # look back at previous segments from the same speaker for a name
            back_text = []
            j = i - 1
            while j >= 0 and len(back_text) < 3:
                if segments[j].get("speaker") == speaker:
                    back_text.insert(0, segments[j].get("text", ""))
                j -= 1
            joined = " ".join(back_text)
            matches = list(_NAME_BEFORE_RE.finditer(joined))
            if matches:
                name = matches[-1].group("name").title()
                name = normalize_recognized_name(name, board_map)
        else:
            m2 = _NAME_ONLY_RE.match(text_l)
            if m2:
                name = m2.group("name").title()
                name = normalize_recognized_name(name, board_map)
            else:
                m3 = _YIELD_RE.search(text_l)
                if m3:
                    name = (m3.group("name") or m3.group("name2")).title()
                    name = normalize_recognized_name(name, board_map)
        if not name:
            continue
        j = i + 1
        while j < len(segments) and segments[j].get("speaker") == speaker:
            j += 1
        if j < len(segments):
            spk = segments[j].get("speaker")
            sub = counts.setdefault(name, {})
            sub[spk] = sub.get(spk, 0) + 1

    speaker_counts: Dict[str, Dict[str, int]] = {}
    for name, spk_counts in counts.items():
        for spk, cnt in spk_counts.items():
            sub = speaker_counts.setdefault(spk, {})
            sub[name] = cnt

    # keep the speaker with the highest count for each name
    name_best: Dict[str, tuple[str, int]] = {}
    for name, spk_counts in counts.items():
        best_spk = max(spk_counts, key=spk_counts.get)
        cnt = spk_counts[best_spk]
        cur = name_best.get(name)
        if not cur or cnt > cur[1]:
            name_best[name] = (best_spk, cnt)


    result: Dict[str, dict] = {spk: {"name": name, "alternatives": []} for name, spk in roll_map.items()}

    if not counts and result:
        return result

    if not counts:
        raise RuntimeError("No recognition cues found – unable to map speakers.")

    for spk, info in result.items():
        speaker_counts.setdefault(spk, {})

    # remove duplicate mappings for the same name
    for name, (best_spk, _) in name_best.items():
        for spk in list(result.keys()):
            if spk != best_spk and result[spk]["name"] == name:
                del result[spk]

    for spk, name_counts in speaker_counts.items():
        if not name_counts:
            continue
        best_name = max(name_counts, key=name_counts.get)
        alt = [n for n in name_counts if n != best_name]
        print(
            f"🔍  Speaker {spk} recognized as {best_name} "
            f"(matches={name_counts[best_name]})"
        )
        if spk in result:
            cur = result[spk]
            if cur["name"] != best_name:
                cur["alternatives"].append(best_name)
                cur["alternatives"].extend([a for a in alt if a != cur["name"]])
            else:
                cur["alternatives"].extend(a for a in alt if a != cur["name"])
        else:
            result[spk] = {"name": best_name, "alternatives": alt}

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


def identify_segments(
    diarized_json: str,
    recognized_map: str = "recognized_map.json",
    out_json: str = "segments_to_keep.json",
    board_file: str | None = None,
) -> None:
    """Create JSON segments for Secretary Nicholson using recognition data."""
    segment_nicholson(
        diarized_json,
        out_json,
        recognized_map=recognized_map,
        board_file=board_file,
    )


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


def _segment_entries(segs_data: List[dict], markup_lines: List[dict]) -> List[dict]:
    """Return Nicholson segments from already parsed transcript entries."""
    nicholson_id = find_nicholson_speaker(segs_data)
    if nicholson_id is None:
        print("❌  Nicholson speaker not found")
        return []

    results = []
    n_idx = [i for i, seg in enumerate(segs_data) if seg.get("speaker") == nicholson_id]
    if not n_idx:
        return []

    groups = []
    start_idx = n_idx[0]
    last_idx = n_idx[0]
    for idx in n_idx[1:]:
        prev_end = float(segs_data[last_idx]["end"])
        cur_start = float(segs_data[idx]["start"])
        if cur_start - prev_end >= MERGE_GAP_SEC:
            groups.append((start_idx, last_idx))
            start_idx = idx
        last_idx = idx
    groups.append((start_idx, last_idx))

    for start_idx, last_idx in groups:
        start_time = float(segs_data[start_idx]["start"])
        end_time = float(segs_data[last_idx]["end"])

        j = last_idx + 1
        next_start = None
        while j < len(segs_data):
            seg = segs_data[j]
            if seg.get("speaker") == nicholson_id:
                break
            text = seg.get("text", "")
            if _recognizes_other(text):
                next_start = (
                    float(segs_data[j + 1]["start"]) if j + 1 < len(segs_data) else float(seg["end"])
                )
                break
            if float(seg["start"]) - end_time >= MERGE_GAP_SEC and should_end(text):
                end_time = float(seg["end"])
                next_start = float(seg["start"])
                break
            end_time = float(seg["end"])
            j += 1

        if next_start is None and j < len(segs_data):
            next_start = float(segs_data[j]["start"])
        if next_start is not None:
            end_time = min(end_time + TRAIL_SEC, next_start)
        else:
            end_time = end_time + TRAIL_SEC

        end_time, segment_lines = trim_segment(start_time, end_time, markup_lines)
        pre_lines = collect_pre(markup_lines, start_time)
        post_lines = collect_post(markup_lines, end_time, next_start)

        results.append(
            {
                "start": round(start_time, 2),
                "end": round(end_time, 2),
                "text": segment_lines,
                "pre": pre_lines,
                "post": post_lines,
            }
        )

    return results


def segment_nicholson_from_transcript(transcript_txt: str, out_json: str = "segments_to_keep.json") -> None:
    """Identify Nicholson segments using ``transcript.txt``."""
    entries = []
    for line in Path(transcript_txt).read_text().splitlines():
        m = _TS_RE.match(line)
        if not m:
            continue
        rest = m.group("rest").strip()
        speaker = ""
        text = rest
        if ":" in rest:
            speaker, text = rest.split(":", 1)
        entries.append(
            {
                "start": float(m.group("start")),
                "end": float(m.group("end")),
                "speaker": speaker.strip(),
                "text": text.strip(),
            }
        )

    markup_lines = load_markup(Path(transcript_txt))
    segs = _segment_entries(entries, markup_lines)
    Path(out_json).write_text(json.dumps(segs, indent=2))
    print(f"✅  {len(segs)} segments → {out_json}")


def collect_pre(segs: List[dict], start: float) -> List[str]:
    window = start - PRE_SEC
    return [s["line"] for s in segs if s["end"] <= start and s["end"] >= window]


def collect_post(segs: List[dict], end: float, next_start: float | None = None) -> List[str]:
    """Return lines after *end* up to the next segment or trailing window."""
    window = end + TRAIL_SEC
    limit = next_start if next_start is not None else window
    if limit <= end or limit > window:
        limit = window
    return [
        l["line"]
        for l in segs
        if l["start"] >= end and l["start"] < limit
    ]


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


def start_score(text: str) -> float:
    txt = text.lower()
    return sum(w for pat, w in _START_SIGNALS.items() if re.search(pat, txt))


def end_score(text: str) -> float:
    txt = text.lower()
    return sum(w for pat, w in _END_SIGNALS.items() if re.search(pat, txt))


def should_start(text: str) -> bool:
    return start_score(text) >= START_THRESHOLD


def should_end(text: str) -> bool:
    return end_score(text) >= END_THRESHOLD


def find_nicholson_speaker(segments: List[dict]) -> str | None:
    for seg in segments:
        spk = seg.get("speaker", "")
        if spk and "nicholson" in spk.lower():
            return spk
    for seg in segments:
        txt = seg.get("text", "").lower()
        if txt.startswith("secretary nicholson") or txt.startswith("director nicholson"):
            return seg.get("speaker")
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


def segment_nicholson(
    diarized_json: str,
    out_json: str = "segments_to_keep.json",
    transcript_pdf: str | None = None,
    tsv_file: str | None = None,
    **_,
) -> None:
    in_path = Path(diarized_json)
    out_path = Path(out_json)

    if transcript_pdf is None:
        transcript_pdf = str(in_path.with_name("transcript.pdf"))
    if tsv_file is None:
        tsv_file = str(in_path.with_suffix(".tsv"))

    use_pdf = Path(transcript_pdf).exists() and Path(tsv_file).exists()

    if use_pdf:
        parse_pdf_order = _parse_pdf_order
        parse_tsv = _parse_tsv
        align_transcript = _align_transcript
        build_segments = _build_segments

        pdf_lines = parse_pdf_order(transcript_pdf)
        tsv_entries = parse_tsv(tsv_file)
        entries = align_transcript(pdf_lines, tsv_entries)
        segs = build_segments(entries)

        out_path.write_text(json.dumps(segs, indent=2))
        print(f"✅  {len(segs)} segments → {out_path}")
        return

    # Fallback to heuristic segmentation using diarized JSON only
    markup_path = in_path.with_name("markup_guide.txt")
    data = json.loads(in_path.read_text())
    segs_data = data["segments"]
    markup_lines = load_markup(markup_path)

    segs = _segment_entries(segs_data, markup_lines)
    if not segs:
        out_path.write_text("[]")
        print("❌  No Nicholson segments found")
        return

    out_path.write_text(json.dumps(segs, indent=2))
    print(f"✅  {len(segs)} segments → {out_path}")


def identify_nicholson_segments(json_file: str, out_json: str = "segments_to_keep.json") -> None:
    """Alias for :func:`segment_nicholson` for backward compatibility."""
    segment_nicholson(json_file, out_json)


def apply_name_map(seg_json: str, map_json: str, out_json: Optional[str] = None) -> None:
    """Replace SPEAKER tokens in *seg_json* with names from *map_json*."""
    segs = json.loads(Path(seg_json).read_text())
    mapping = json.loads(Path(map_json).read_text())
    repl = {k: v.get("name", k) for k, v in mapping.items()}
    for seg in segs:
        for key in ["text", "pre", "post"]:
            lines = seg.get(key, [])
            new_lines = []
            for line in lines:
                for spk, name in repl.items():
                    line = line.replace(spk, name)
                new_lines.append(line)
            seg[key] = new_lines
    Path(out_json or seg_json).write_text(json.dumps(segs, indent=2))
    print(f"✅  names applied → {out_json or seg_json}")


def apply_name_map_json(json_file: str, map_json: str, out_json: Optional[str] = None) -> None:
    """Replace SPEAKER tokens in a diarized JSON transcript using *map_json*."""
    data = json.loads(Path(json_file).read_text())
    mapping = json.loads(Path(map_json).read_text())
    repl = {k: v.get("name", k) for k, v in mapping.items()}
    for seg in data.get("segments", []):
        spk = seg.get("speaker")
        if spk in repl:
            seg["speaker"] = repl[spk]
        text = seg.get("text")
        if text:
            for key, val in repl.items():
                text = text.replace(key, val)
            seg["text"] = text
    Path(out_json or json_file).write_text(json.dumps(data, indent=2))
    print(f"✅  transcript names applied → {out_json or json_file}")


def prune_segments(seg_json: str, out_json: Optional[str] = None) -> None:
    """Remove trivial segments with very few words."""
    segs = json.loads(Path(seg_json).read_text())
    kept = []
    for seg in segs:
        words = " ".join(seg.get("text", [])).split()
        if len(words) >= 4:
            kept.append(seg)
    Path(out_json or seg_json).write_text(json.dumps(kept, indent=2))
    print(f"✅  {len(kept)} segment(s) kept → {out_json or seg_json}")


def generate_recognized_directors(
    recognized_map: str,
    board_file: str = str(BOARD_FILE),
    out_file: str = "recognized_directors.txt",
) -> None:
    """Write recognized directors matched against the official board list."""
    board = load_board_names(board_file)
    mapping = json.loads(Path(recognized_map).read_text())
    found = []
    for info in mapping.values():
        name = info.get("name", "")
        match = get_close_matches(name.lower(), list(board), n=1, cutoff=0.75)
        if match:
            found.append(match[0])
    Path(out_file).write_text("\n".join(sorted(set(found))) + "\n")
    print(f"✅  recognized directors → {out_file}")

__all__ = [
    "map_nicholson_speaker",
    "map_speaker_by_phrases",
    "map_recognized_speakers",
    "map_recognized_auto",
    "add_speaker_labels",
    "auto_segments_for_speaker",
    "segment_nicholson_from_transcript",
    "identify_nicholson_segments",
    "identify_segments",
    "find_nicholson_speaker",
    "segment_nicholson",
    "apply_name_map",
    "apply_name_map_json",
    "prune_segments",
    "generate_recognized_directors",
    "load_board_names",
    "load_board_map",
    "normalize_recognized_name",
    "start_score",
    "end_score",
    "should_start",
    "should_end",
]

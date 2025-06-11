"""Nicholson segmentation helpers."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
from functools import reduce
from difflib import get_close_matches

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
    recognized_map: str | None = None,
    board_file: str | None = None,
    transcript_pdf: str | None = None,
) -> None:
    in_path = Path(diarized_json)
    out_path = Path(out_json)
    markup_path = in_path.with_name("markup_guide.txt")


    data = json.loads(in_path.read_text())
    segs = data["segments"]
    pdf_name_map: Dict[str, str] = {}
    if transcript_pdf:
        try:
            from . import pdf_utils
            dialog = pdf_utils.extract_transcript_dialogue(transcript_pdf)
            for seg, (name, _) in zip(segs, dialog):
                pdf_name_map.setdefault(seg.get("speaker"), name.title())
        except Exception:
            pdf_name_map = {}
    markup_lines = load_markup(markup_path)
    board_names = load_board_names(board_file)

    recog_ids: List[str] | None = None
    name_map: Dict[str, str] = {}
    if recognized_map and Path(recognized_map).exists():
        try:
            mapping = json.loads(Path(recognized_map).read_text())
            try:
                from . import pdf_utils
                mapping = pdf_utils.clean_recognized_map(
                    mapping,
                    board_file=board_file,
                    pdf_path=transcript_pdf,
                )
            except Exception:
                pass
            name_map = {spk: info.get("name", "") for spk, info in mapping.items()}
            recog_ids = [
                spk
                for spk, info in mapping.items()
                if "nicholson" in str(info.get("name", "")).lower()
            ]
        except Exception:
            recog_ids = None
            name_map = {}

    for spk, n in pdf_name_map.items():
        name_map.setdefault(spk, n)

    heur_id = find_nicholson_speaker(segs)
    if heur_id is None:
        heur_id = map_nicholson_speaker(str(in_path))

    if not recog_ids:
        recog_ids = [spk for spk, n in name_map.items() if "nicholson" in n.lower()]

    nicholson_ids = recog_ids or [heur_id]

    if recog_ids:
        if heur_id in recog_ids:
            print(
                f"🔍  Nicholson IDs agree ({heur_id})"
            )
        else:
            print(
                f"⚠️  recognition map {recog_ids} disagrees with heuristic {heur_id}"
            )
    print(f"🔍  Secretary Nicholson identified as {', '.join(nicholson_ids)}")

    results = []
    n_idx = [i for i, seg in enumerate(segs) if seg.get("speaker") in nicholson_ids]
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
        prev_text = segs[idx - 1].get("text", "") if idx > 0 else ""
        if cur_start - prev_end > MERGE_GAP_SEC or should_start(prev_text):
            groups.append((start_idx, last_idx))
            start_idx = idx
        last_idx = idx
    groups.append((start_idx, last_idx))

    for gi, (start_idx, last_idx) in enumerate(groups):
        start_time = float(segs[start_idx]["start"])
        if gi + 1 < len(groups):
            next_start = float(segs[groups[gi + 1][0]]["start"])
            end_time = next_start
        else:
            end_time = float(segs[last_idx]["end"])

            j = last_idx + 1
            next_start = None
            prev_spk = None
            while j < len(segs):
                seg = segs[j]
                seg_start = float(seg["start"])
                seg_end = float(seg["end"])
                spk = seg.get("speaker")
                if spk in nicholson_ids:
                    break
                name = name_map.get(spk, "")
                is_director = _is_board_member(name, board_names)
                if not name and not is_director:
                    end_time = seg_end
                    if (not board_names or not name_map) and prev_spk is not None and spk != prev_spk:
                        next_start = seg_start
                        break
                    prev_spk = spk
                    j += 1
                    continue
                if should_end(seg.get("text", "")) or seg_start - float(segs[last_idx]["end"]) >= END_GAP_SEC:
                    end_time = seg_end
                    next_start = seg_start
                    break
                if is_director:
                    next_start = seg_start
                    break
                if not board_names or not name_map:
                    if prev_spk is not None and spk != prev_spk:
                        next_start = seg_start
                        break
                    prev_spk = spk
                end_time = seg_end
                j += 1
            if j < len(segs):
                if next_start is None:
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

    if name_map:
        repl = {k: v for k, v in name_map.items() if v}
        for seg in results:
            for key in ["text", "pre", "post"]:
                seg[key] = [
                    reduce(lambda s, p: s.replace(p[0], p[1]), repl.items(), line)
                    for line in seg.get(key, [])
                ]

    out_path.write_text(json.dumps(results, indent=2))
    print(f"✅  {len(results)} segments → {out_path}")


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

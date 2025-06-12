import csv
import json
import re
from pathlib import Path

import pdfminer.high_level

_norm_re = re.compile(r"\s+")

def normalize(text: str) -> str:
    return _norm_re.sub(" ", text.strip()).lower()


def parse_pdf_order(pdf_path: str):
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


def parse_tsv(tsv_path: str):
    """Return list of transcript entries."""
    entries = []
    with open(tsv_path) as f:
        next(f)
        reader = csv.reader(f, delimiter="\t")
        for start, end, text in reader:
            entries.append(
                {
                    "start": float(start) / 1000.0,
                    "end": float(end) / 1000.0,
                    "text": text.strip(),
                }
            )
    return entries


def align_transcript(pdf_lines, tsv_entries):
    """Return transcript entries with an assigned speaker from the PDF."""
    j = 0
    for entry in tsv_entries:
        target = normalize(entry["text"])
        for k in range(j, len(pdf_lines)):
            spk, txt = pdf_lines[k]
            if target in normalize(txt):
                entry["speaker"] = spk
                j = k
                break
        else:
            entry["speaker"] = ""
    return tsv_entries


def build_segments(entries, gap=20):
    """Return highlight reel segments including discussion with Nicholson."""
    segments = []
    active = False
    start_time = None
    last_nich = None
    end_time = None
    for ent in entries:
        text_l = ent["text"].lower()
        spk_l = ent.get("speaker", "").lower()
        is_nich = "nicholson" in text_l or spk_l.startswith("chris nicholson")

        if is_nich:
            if not active:
                start_time = max(0.0, ent["start"] - 5)
                active = True
            last_nich = ent["end"]
            end_time = ent["end"]
        elif active:
            if ent["start"] - (last_nich or ent["start"]) <= gap:
                end_time = ent["end"]
            else:
                segments.append({"start": start_time, "end": (last_nich or end_time) + 10})
                active = False
                start_time = None
                last_nich = None
                end_time = None
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





def main():
    pdf = 'videos/May_Board_Meeting/transcript.pdf'
    tsv = 'videos/May_Board_Meeting/May_Board_Meeting.tsv'
    out_json = 'videos/May_Board_Meeting/segments_to_keep.json'
    pdf_lines = parse_pdf_order(pdf)
    tsv_entries = parse_tsv(tsv)
    entries = align_transcript(pdf_lines, tsv_entries)
    segs = build_segments(entries)
    Path(out_json).write_text(json.dumps(segs, indent=2))
    print(f'Written {out_json} with {len(segs)} segments')


if __name__ == '__main__':
    main()

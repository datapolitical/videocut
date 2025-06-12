import re
from pathlib import Path

SRC = Path('videos/May_Board_Meeting/pdf_lines.txt')
DST = Path('videos/May_Board_Meeting/segments_from_pdf.txt')

lines = SRC.read_text().splitlines()

segments = []
start = None
pending_end = None
in_segment = False

for i, line in enumerate(lines):
    is_nich = 'nicholson' in line.lower()
    if is_nich:
        if not in_segment:
            start = max(i - 1, 0)
            in_segment = True
        pending_end = i + 2
    elif in_segment:
        if i > pending_end:
            segments.append((start, min(pending_end, len(lines) - 1)))
            in_segment = False
            start = None
            pending_end = None

if in_segment:
    segments.append((start, min(pending_end, len(lines) - 1)))

# merge segments if overlapping or touching
merged = []
for s, e in segments:
    if merged and s <= merged[-1][1] + 1:
        merged[-1] = (merged[-1][0], max(merged[-1][1], e))
    else:
        merged.append((s, e))

out_lines = []
seg_idx = 0
for i, line in enumerate(lines):
    if seg_idx < len(merged) and i == merged[seg_idx][0]:
        out_lines.append("=START=")
    out_lines.append("\t" + line)
    if seg_idx < len(merged) and i == merged[seg_idx][1]:
        out_lines.append("=END=")
        seg_idx += 1

DST.write_text("\n".join(out_lines) + "\n")
print(f"Wrote {DST} with {len(merged)} segments")

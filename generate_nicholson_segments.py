import re
from pathlib import Path

SRC = Path('videos/May_Board_Meeting/pdf_lines.txt')
DST = Path('videos/May_Board_Meeting/segments_from_pdf.txt')
BOARD_FILE = Path('board_members.txt')

line_re = re.compile(r'^(?P<time>\d{2}:\d{2}:\d{2}\.\d{3})\s+(?P<speaker>[^:]+):\s*(?P<text>.*)$')

board_names = [ln.strip() for ln in BOARD_FILE.read_text().splitlines() if ln.strip()]
last_names = {name.split()[-1] for name in board_names if name}
board_pat = re.compile(r'\b(' + '|'.join(re.escape(n) for n in last_names) + r')\b', re.IGNORECASE)

lines = SRC.read_text().splitlines()
segments = []
i = 0
while i < len(lines):
    m = line_re.match(lines[i])
    if not m:
        i += 1
        continue
    speaker = m.group('speaker')
    text = m.group('text')
    if 'nicholson' in speaker.lower():
        start = max(i - 1, 0)
        j = i + 1
        while j < len(lines):
            m2 = line_re.match(lines[j])
            if not m2:
                j += 1
                continue
            spk2 = m2.group('speaker')
            text2 = m2.group('text')
            if board_pat.search(text2) and 'nicholson' not in text2.lower():
                break
            if re.search(r'next item|moving on|that concludes', text2, re.IGNORECASE):
                break
            j += 1
        segments.append((start, j - 1))
        i = j
    else:
        i += 1

# merge overlapping segments
merged = []
for s, e in segments:
    if merged and s <= merged[-1][1] + 1:
        merged[-1] = (merged[-1][0], max(merged[-1][1], e))
    else:
        merged.append((s, e))

out_lines = []
seg_iter = iter(merged)
current = next(seg_iter, None)
for idx, line in enumerate(lines):
    if current and idx == current[0]:
        out_lines.append("=START=")
    out_lines.append('\t' + line)
    if current and idx == current[1]:
        out_lines.append("=END=")
        current = next(seg_iter, None)

DST.write_text('\n'.join(out_lines) + '\n')
print(f"Wrote {len(merged)} segments to {DST}")

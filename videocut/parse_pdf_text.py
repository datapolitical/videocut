import re
from pathlib import Path
from pdfminer.high_level import extract_text

# Stop parsing once any of these patterns are encountered. The PDF contains
# appended public comment emails after the actual meeting transcript which
# begin with these headers.
STOP_PREFIXES = (
    "PUBLIC COMMENT",
    "Cc:",
    "Note:",
    "Warning:",
    "Re:",
    "Date:",
    "To:",
    "From:",
)

DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")
SPEAKER_RE = re.compile(r"^([A-Z][A-Z'\- ]+):\s*(.*)")


def parse_pdf(pdf_path: str) -> list[str]:
    """Return cleaned transcript lines."""
    text = extract_text(pdf_path)
    lines = []
    current = None
    raw_lines = text.splitlines()
    i = 0
    while i < len(raw_lines):
        line = re.sub(r"\s+", " ", raw_lines[i].strip())
        i += 1
        if not line:
            continue
        # Detect the start of the public comment section.  Occasionally a
        # speaker's line may span a page break and begin with the words
        # "PUBLIC COMMENT".  Treat it as the actual public comment section only
        # when it is followed by a date on the same line or the next line.
        if line.upper().startswith("PUBLIC COMMENT"):
            has_date = bool(DATE_RE.search(line))
            j = i
            while not has_date and j < len(raw_lines):
                next_line = re.sub(r"\s+", " ", raw_lines[j].strip())
                j += 1
                if not next_line:
                    continue
                has_date = bool(DATE_RE.search(next_line))
                break
            if has_date:
                if current:
                    if not lines or lines[-1] != current:
                        lines.append(current)
                    current = None
                break
        # Older PDFs include public comment email headers at the very end.
        # They usually appear after the bulk of the meeting, so keep the
        # original heuristic for those prefixes once a substantial amount of
        # lines has been processed.
        if len(lines) > 500 and any(line.startswith(p) for p in STOP_PREFIXES):
            if current:
                if not lines or lines[-1] != current:
                    lines.append(current)
                current = None
            break
        m = SPEAKER_RE.match(line)
        if m:
            if current:
                lines.append(current)
            speaker = m.group(1).title()
            current = f"{speaker}: {m.group(2).strip()}"
        else:
            if current:
                current += f" {line.strip()}"
    if current:
        lines.append(current)
    return lines


def main():
    pdf = "videos/May_Board_Meeting/transcript.pdf"
    out_txt = "videos/May_Board_Meeting/pdf_lines.txt"
    lines = parse_pdf(pdf)
    Path(out_txt).write_text("\n".join(lines) + "\n")
    print(f"Wrote {len(lines)} lines to {out_txt}")


if __name__ == "__main__":
    main()

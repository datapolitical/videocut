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

SPEAKER_RE = re.compile(r"^([A-Z][A-Z'\- ]+):\s*(.*)")


def parse_pdf(pdf_path: str) -> list[str]:
    """Return cleaned transcript lines."""
    text = extract_text(pdf_path)
    lines = []
    current = None
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw.strip())
        if not line:
            continue
        # The PDF contains scanned public comment letters after the end of the
        # meeting transcript. These lines begin with headers like "Cc:" or
        # "Public Comment" and should be ignored. They appear only after the
        # main transcript, so we only check for them once we've processed most
        # of the meeting.
        if len(lines) > 500 and (any(line.startswith(p) for p in STOP_PREFIXES) or "PUBLIC COMMENT" in line.upper()):
            if current:
                lines.append(current)
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

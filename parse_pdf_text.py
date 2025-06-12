import re
from pathlib import Path
from pdfminer.high_level import extract_text

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

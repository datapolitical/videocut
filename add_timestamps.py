import json
from pathlib import Path


def format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def main():
    json_path = Path("videos/May_Board_Meeting/May_Board_Meeting.json")
    lines_path = Path("videos/May_Board_Meeting/pdf_lines.txt")
    out_path = Path("videos/May_Board_Meeting/pdf_lines.txt")

    segments = json.loads(json_path.read_text())
    segs = segments.get("segments", [])
    lines = lines_path.read_text().splitlines()

    n = min(len(lines), len(segs))
    new_lines = []
    for i in range(n):
        ts = format_timestamp(segs[i]["start"])
        new_lines.append(f"{ts} {lines[i]}")
    for i in range(n, len(lines)):
        new_lines.append(f"00:00:00.000 {lines[i]}")

    out_path.write_text("\n".join(new_lines) + "\n")
    print(f"Wrote {len(new_lines)} lines to {out_path}")


if __name__ == "__main__":
    main()

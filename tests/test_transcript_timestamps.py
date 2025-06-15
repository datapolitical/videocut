import shutil
import re
from pathlib import Path

from videocut.core import pdf_utils


def test_timestamped_transcript_has_times(tmp_path):
    base = Path("videos/May_Board_Meeting")
    json_src = base / "May_Board_Meeting.json"
    pdf_file = base / "transcript.pdf"
    srt_file = base / "May_Board_Meeting.srt"

    json_copy = tmp_path / "May_Board_Meeting.json"
    shutil.copy(json_src, json_copy)

    pdf_utils.apply_pdf_transcript_json(str(json_copy), str(pdf_file))

    out_txt = tmp_path / "transcript.txt"
    pdf_utils.write_timestamped_transcript(
        str(pdf_file),
        str(srt_file),
        str(out_txt),
        json_path=str(json_copy),
    )

    lines = out_txt.read_text().splitlines()
    ts_re = re.compile(r"\[(\d+\.\d+)-(\d+\.\d+)\]")
    assert lines
    for line in lines:
        m = ts_re.search(line)
        assert m, f"missing timestamp: {line}"
        start, end = float(m.group(1)), float(m.group(2))
        assert not (start == 0 and end == 0), f"timestamp not set: {line}"

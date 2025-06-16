from pathlib import Path
from videocut.core.align import align_pdf_to_asr


def test_alignment_smoke():
    matched = align_pdf_to_asr(
        Path("videos/May_Board_Meeting/pdf_transcript.json"),
        Path("videos/May_Board_Meeting/May_Board_Meeting.json"),
        window=120,
        step=30,
        ratio_thresh=0.0,
    )
    assert matched, "No output"
    assert sum(x["start"] is None for x in matched) < 20, "Too many misses"

def test_three_stage_alignment():
    matched = align_pdf_to_asr(
        Path("pdf_transcript.json"),
        Path("May_Board_Meeting.json"),
        window=120, step=30, ratio_thresh=0.15,
    )
    assert len(matched) > 0
    assert all("start" in m and "end" in m for m in matched)
    assert all(m["start"] is not None and m["end"] is not None for m in matched)

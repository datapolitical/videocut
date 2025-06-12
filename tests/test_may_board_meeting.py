import json
from pathlib import Path

from videocut.core import nicholson


def test_may_board_meeting_segments(tmp_path):
    base = Path("videos/May_Board_Meeting")
    input_json = base / "prior_files" / "May_Board_Meeting.json"
    out_json = tmp_path / "segments.json"

    # The sample directory no longer includes a recognized_map.json file, so the
    # segmentation routine should run without one.
    nicholson.segment_nicholson(
        str(input_json),
        str(out_json),
    )

    result = json.loads(out_json.read_text())
    assert isinstance(result, list)
    assert result  # segments were produced

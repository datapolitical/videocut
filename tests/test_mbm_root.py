import json
from pathlib import Path
from videocut.core import nicholson

def test_mbm_root_segments(tmp_path):
    input_json = Path('videos/May_Board_Meeting/May_Board_Meeting.json')
    out_json = tmp_path / 'segments.json'
    nicholson.segment_nicholson(str(input_json), str(out_json))
    result = json.loads(out_json.read_text())
    assert isinstance(result, list)
    assert result

import json
from pathlib import Path
from videocut.core import pdf_utils

def test_apply_pdf_transcript_truncates(tmp_path, monkeypatch):
    data = {
        "segments": [
            {"start": 0, "end": 1, "label": "A", "text": "foo"},
            {"start": 1, "end": 2, "label": "B", "text": "bar"},
            {"start": 2, "end": 3, "label": "C", "text": "baz"},
        ]
    }
    json_file = tmp_path / "dia.json"
    json_file.write_text(json.dumps(data))
    pdf_file = tmp_path / "t.pdf"
    pdf_file.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(pdf_utils, "extract_transcript_dialogue", lambda p: [("X", "l1"), ("Y", "l2")])

    pdf_utils.apply_pdf_transcript_json(str(json_file), str(pdf_file))

    result = json.loads(json_file.read_text())
    assert len(result["segments"]) == 2
    assert result["segments"][0]["label"] == "X"
    assert result["segments"][0]["text"] == "l1"
    assert result["segments"][1]["label"] == "Y"
    assert result["segments"][1]["text"] == "l2"

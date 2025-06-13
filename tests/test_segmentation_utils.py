import os, sys, json
from pathlib import Path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import pytest
from videocut.core import segmentation, nicholson
import importlib.util, pathlib, sys
_cli_path = pathlib.Path(__file__).resolve().parents[1]/"videocut"/"cli.py"
_spec = importlib.util.spec_from_file_location("videocut.cli", _cli_path)
videocut_cli = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = videocut_cli
_spec.loader.exec_module(videocut_cli)

def test_identify_clips_json(tmp_path, capsys):
    segs = [
        {"start": 0, "end": 1, "keep": True},
        {"start": 1, "end": 2, "keep": False},
        {"start": 2, "end": 3, "keep": "x"},
    ]
    edit = tmp_path / "edit.json"
    edit.write_text(json.dumps(segs))
    out = tmp_path / "keep.json"

    segmentation.identify_clips_json(str(edit), str(out))

    result = json.loads(out.read_text())
    assert result == [{"start": 0.0, "end": 1.0}, {"start": 2.0, "end": 3.0}]
    assert "✅" in capsys.readouterr().out


def test_identify_clips_json_missing(tmp_path):
    with pytest.raises(SystemExit):
        segmentation.identify_clips_json(str(tmp_path / "missing.json"), str(tmp_path / "out.json"))


def test_extract_marked(tmp_path, capsys):
    markup = tmp_path / "markup_guide.txt"
    markup.write_text("\n".join([
        "[0-5] intro",
        "[6-10] part",
        "START [20-",
        "something",
        "END [20-25]",
    ]))
    out = tmp_path / "segments.json"
    segmentation.extract_marked(str(markup), str(out))

    segs = json.loads(out.read_text())
    assert segs == [
        {"start": 0.0, "end": 5.0},
        {"start": 6.0, "end": 10.0},
        {"start": 20.0, "end": 25.0},
    ]
    assert "✅" in capsys.readouterr().out


def test_identify_segments(tmp_path, capsys):
    diarized = tmp_path / "dia.json"
    diarized.write_text(json.dumps({
        "segments": [
            {"start": 0, "end": 1, "speaker": "A", "text": "secretary nicholson welcome"},
            {"start": 1, "end": 2, "speaker": "B", "text": "other"},
            {"start": 2, "end": 3, "speaker": "A", "text": "continue"},
        ]
    }))
    out = tmp_path / "keep.json"

    nicholson.identify_segments(str(diarized), out_json=str(out))

    segs = json.loads(out.read_text())
    assert len(segs) == 1
    assert segs[0]["start"] == pytest.approx(0.0)
    assert segs[0]["end"] == pytest.approx(33.0)
    assert "✅" in capsys.readouterr().out



def test_cli_commands(tmp_path):
    edit = tmp_path / "edit.json"
    edit.write_text(json.dumps([{"start": 0, "end": 1, "keep": True}]))
    markup = tmp_path / "markup_guide.txt"
    markup.write_text("[0-1] hi")
    diarized = tmp_path / "dia.json"
    diarized.write_text(json.dumps({"segments": [{"start": 0, "end": 1, "speaker": "A", "text": "secretary nicholson"}]}))

    out1 = tmp_path / "keep1.json"
    videocut_cli.identify_clips_json(edit_json=str(edit), out=str(out1))
    assert out1.exists()

    out2 = tmp_path / "keep2.json"
    videocut_cli.extract_marked(markup=str(markup), out=str(out2))
    assert out2.exists()

    transcript = tmp_path / "transcript.txt"
    transcript.write_text("[0-1] Nicholson: hi\n[1-2] Other: bye\n")

    cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        videocut_cli.identify_segments_cmd(transcript=str(transcript))
    finally:
        os.chdir(cwd)
    assert (tmp_path / "segments.txt").exists()


def test_json_to_editable_list(tmp_path, capsys):
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps([{"start": 0, "end": 1, "text": "hi"}]))
    out = tmp_path / "edit.json"

    segmentation.json_to_editable(str(raw), str(out))

    result = json.loads(out.read_text())
    assert result[0]["id"] == 1
    assert result[0]["content"] == "hi"
    assert "keep" in result[0]
    assert "✅" in capsys.readouterr().out


def test_json_to_tsv_list(tmp_path, capsys):
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps([{"start": 0, "end": 1, "speaker": "S", "text": "hi"}]))
    out = tmp_path / "out.tsv"

    segmentation.json_to_tsv(str(raw), str(out))

    lines = out.read_text().splitlines()
    assert lines[0] == "start\tend\tspeaker\ttext\tkeep"
    assert lines[1].startswith("0\t1\tS\thi\t")
    assert "✅" in capsys.readouterr().out


def test_segments_txt_roundtrip(tmp_path):
    segs = [
        {"text": ["[0-1] A: hi", "[1-2] B: there"]},
        {"text": ["[2-3] A: bye"]},
    ]
    js = tmp_path / "segs.json"
    js.write_text(json.dumps(segs))

    txt = tmp_path / "segments.txt"
    segmentation.segments_json_to_txt(str(js), str(txt))

    lines = txt.read_text().splitlines()
    assert lines[0] == "=START="
    assert lines[1].startswith("\t[1]")

    pairs = segmentation.segments_from_txt(str(txt))
    assert pairs == [(1, 2), (3, 3)]

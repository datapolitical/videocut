import shutil
import json
import importlib.util
import pathlib
import sys

_cli_path = pathlib.Path(__file__).resolve().parents[1] / "videocut" / "cli.py"
_spec = importlib.util.spec_from_file_location("videocut.cli", _cli_path)
videocut_cli = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = videocut_cli
_spec.loader.exec_module(videocut_cli)


def test_segment_cli(tmp_path, monkeypatch):
    src = pathlib.Path("videos/May_Board_Meeting/May_Board_Meeting.json")
    work_json = tmp_path / "videos" / "May_Board_Meeting.json"
    work_json.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, work_json)
    monkeypatch.chdir(tmp_path)

    videocut_cli.segment(json_file=str(work_json))

    seg_txt = tmp_path / "segments.txt"
    assert seg_txt.exists()
    lines = seg_txt.read_text().splitlines()
    assert lines
    assert any(l == "=START=" for l in lines)
    assert any(l == "=END=" for l in lines)
    assert any(l.startswith("[") for l in lines if l != "=START=" and l != "=END=")
    assert lines.count("=START=") == lines.count("=END=")

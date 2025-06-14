import json
import shutil
import pathlib
import importlib.util
import sys
import re

_cli_path = pathlib.Path(__file__).resolve().parents[1] / "videocut" / "cli.py"
_spec = importlib.util.spec_from_file_location("videocut.cli", _cli_path)
videocut_cli = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = videocut_cli
_spec.loader.exec_module(videocut_cli)

def test_segments_format(tmp_path, monkeypatch):
    src = pathlib.Path("videos/May_Board_Meeting/May_Board_Meeting.json")
    work = tmp_path / "May_Board_Meeting.json"
    shutil.copy(src, work)
    monkeypatch.chdir(tmp_path)

    videocut_cli.segment(json_file=str(work))

    seg_txt = tmp_path / "segments.txt"
    assert seg_txt.exists() and seg_txt.read_text().strip()

    lines = seg_txt.read_text().splitlines()
    assert any(l == "=START=" for l in lines)
    assert any(l == "=END=" for l in lines)

    indented = [l for l in lines if l.startswith("\t")]
    plain = [l for l in lines if l and not l.startswith("\t") and l not in {"=START=", "=END="}]
    assert indented
    assert plain

    pattern = re.compile(r"^\[\d+\.\d+ - \d+\.\d+\] .+?: .+")
    for l in lines:
        if l in {"=START=", "=END="}:
            continue
        assert pattern.match(l.lstrip("\t"))

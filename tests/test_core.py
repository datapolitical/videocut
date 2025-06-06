import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import videocut.core.transcription as transcribe_mod
import videocut.core.video_editing as video_editing


def test_transcribe_creates_markup(tmp_path, monkeypatch):
    json_out = tmp_path / "input.json"

    calls = {}

    def fake_run(cmd, check, env=None):
        calls["cmd"] = cmd
        json_out.write_text(json.dumps({"segments": [{"start": 0, "end": 1, "text": "hi"}]}))
        return SimpleNamespace(returncode=0)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(transcribe_mod, "is_apple_silicon", lambda: False)
    monkeypatch.setattr(transcribe_mod.subprocess, "run", fake_run)

    transcribe_mod.transcribe("input.mp4")

    assert calls["cmd"][3] == "float16"  # compute_type
    guide = Path("markup_guide.txt").read_text().strip()
    assert guide == "[0-1] SPEAKER: hi"


def test_generate_clips_invokes_ffmpeg(tmp_path, monkeypatch):
    seg_file = tmp_path / "segments.json"
    seg_file.write_text(json.dumps([{"start": 0, "end": 1}]))

    calls = {"run": [], "build": []}

    def fake_run(cmd, check, env=None):
        calls["run"].append(cmd)
        Path(cmd[-1]).write_text("tmp")

    def fake_build(src, dst):
        calls["build"].append((src, dst))
        dst.write_text("done")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(video_editing.subprocess, "run", fake_run)
    monkeypatch.setattr(video_editing, "_build_faded_clip", fake_build)

    video_editing.generate_clips("vid.mp4", str(seg_file), "clips")

    assert calls["run"]  # ffmpeg called
    assert calls["build"]  # faded clip built
    assert (tmp_path / "clips" / "clip_000.mp4").exists()

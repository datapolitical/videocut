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
    assert (tmp_path / "input.tsv").exists()


def test_transcribe_with_pdf(tmp_path, monkeypatch):
    json_out = tmp_path / "input.json"
    srt_out = tmp_path / "input.srt"

    def fake_run(cmd, check, env=None):
        json_out.write_text(json.dumps({"segments": [{"start": 0, "end": 1, "text": "hi"}]}))
        srt_out.write_text("1\n00:00:00,000 --> 00:00:01,000\nHi\n")
        return SimpleNamespace(returncode=0)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(transcribe_mod, "is_apple_silicon", lambda: False)
    monkeypatch.setattr(transcribe_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(transcribe_mod.pdf_utils, "apply_pdf_transcript_json", lambda j, p, o=None: None)
    monkeypatch.setattr(transcribe_mod.pdf_utils, "write_timestamped_transcript", lambda p, s, out: Path(out).write_text("done"))
    monkeypatch.setattr(transcribe_mod.segmentation, "json_to_tsv", lambda j, o: Path(o).write_text("tsv"))

    transcribe_mod.transcribe("input.mp4", pdf_path="t.pdf")

    assert (tmp_path / "transcript.txt").exists()


def test_generate_clips_invokes_ffmpeg(tmp_path, monkeypatch):
    seg_file = tmp_path / "segments.json"
    seg_file.write_text(json.dumps([{"start": 0, "end": 1}]))

    calls = {"run": [], "build": [], "align": []}

    def fake_run(cmd, check, env=None):
        calls["run"].append(cmd)
        Path(cmd[-1]).write_text("tmp")

    def fake_build(src, dst):
        calls["build"].append((src, dst))
        dst.write_text("done")

    def fake_align(video, transcript, out_json):
        calls["align"].append((video, transcript, out_json))
        Path(out_json).write_text(json.dumps([{"text": "hi", "start": 0.0, "end": 1.0}]))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(video_editing.subprocess, "run", fake_run)
    monkeypatch.setattr(video_editing, "_build_faded_clip", fake_build)
    monkeypatch.setattr(video_editing.alignment, "align_with_transcript", fake_align)

    video_editing.generate_clips("vid.mp4", str(seg_file), "clips")

    assert calls["run"]  # ffmpeg called
    assert calls["build"]  # faded clip built
    assert (tmp_path / "clips" / "clip_000.mp4").exists()


def test_generate_clips_segments_txt(tmp_path, monkeypatch):
    srt = tmp_path / "input.srt"
    srt.write_text("""1\n00:00:00,000 --> 00:00:01,000\nA\n\n2\n00:00:01,000 --> 00:00:02,000\nB\n""")
    seg_txt = tmp_path / "segments.txt"
    seg_txt.write_text("=START=\n\t[1]A\n\t[2]B\n=END=\n")

    calls = {"run": [], "build": [], "align": []}

    def fake_run(cmd, check, env=None):
        calls["run"].append(cmd)
        Path(cmd[-1]).write_text("tmp")

    def fake_build(src, dst):
        calls["build"].append((src, dst))
        dst.write_text("done")

    def fake_align(video, transcript, out_json):
        calls["align"].append((video, transcript, out_json))
        Path(out_json).write_text(json.dumps([{"text": "hi", "start": 0.0, "end": 1.0}]))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(video_editing.subprocess, "run", fake_run)
    monkeypatch.setattr(video_editing, "_build_faded_clip", fake_build)
    monkeypatch.setattr(video_editing.alignment, "align_with_transcript", fake_align)

    video_editing.generate_clips("vid.mp4", str(seg_txt), "clips", str(srt))

    assert calls["run"]
    assert calls["build"]
    assert calls["align"]
    assert (tmp_path / "clips" / "clip_000.mp4").exists()
    assert (tmp_path / "clips" / "clip_000_aligned.json").exists()
    ts = json.loads((tmp_path / "clips" / "timestamps.json").read_text())
    assert "clip_000" in ts

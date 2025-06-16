import pathlib, importlib.util, sys

_cli_path = pathlib.Path(__file__).resolve().parents[1] / "videocut" / "cli.py"
_spec = importlib.util.spec_from_file_location("videocut.cli", _cli_path)
videocut_cli = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = videocut_cli
_spec.loader.exec_module(videocut_cli)

import videocut.core.video_editing as video_editing


def test_generate_and_align_cli(tmp_path, monkeypatch):
    seg_txt = tmp_path / "segments.txt"
    seg_txt.write_text("=START=\n[1] hi\n=END=\n")
    srt = tmp_path / "input.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")

    called = {}

    def fake_generate(video, segs, out_dir, srt_file=None):
        called["args"] = (video, segs, out_dir, srt_file)

    monkeypatch.setattr(video_editing, "generate_and_align", fake_generate)
    monkeypatch.chdir(tmp_path)

    videocut_cli.generate_and_align(video="input.mp4", segs=str(seg_txt), srt_file=str(srt))

    assert called["args"][0] == "input.mp4"
    assert called["args"][1] == str(seg_txt)
    assert called["args"][3] == str(srt)


def test_clip_cli(tmp_path, monkeypatch):
    seg_json = tmp_path / "segments.json"
    seg_json.write_text("[]")

    called = {}

    def fake_clip(video, segs, out_dir, srt_file=None):
        called["args"] = (video, segs, out_dir, srt_file)

    monkeypatch.setattr(video_editing, "clip_segments", fake_clip)
    monkeypatch.chdir(tmp_path)

    videocut_cli.clip_cmd(video="input.mp4", segs=str(seg_json))

    assert called["args"][0] == "input.mp4"
    assert called["args"][1] == str(seg_json)

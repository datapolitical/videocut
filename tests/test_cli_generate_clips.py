import pathlib, importlib.util, sys

_cli_path = pathlib.Path(__file__).resolve().parents[1] / "videocut" / "cli.py"
_spec = importlib.util.spec_from_file_location("videocut.cli", _cli_path)
videocut_cli = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = videocut_cli
_spec.loader.exec_module(videocut_cli)

import videocut.core.video_editing as video_editing


def test_generate_clips_cli(tmp_path, monkeypatch):
    seg_txt = tmp_path / "segments.txt"
    seg_txt.write_text("=START=\n[1] hi\n=END=\n")
    srt = tmp_path / "input.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")

    called = {}

    def fake_generate(video, segs, out_dir, srt_file=None):
        called["args"] = (video, segs, out_dir, srt_file)

    monkeypatch.setattr(video_editing, "generate_clips", fake_generate)
    monkeypatch.chdir(tmp_path)

    videocut_cli.generate_clips(video="input.mp4", segs=str(seg_txt), srt_file=str(srt))

    assert called["args"][0] == "input.mp4"
    assert called["args"][1] == str(seg_txt)
    assert called["args"][3] == str(srt)

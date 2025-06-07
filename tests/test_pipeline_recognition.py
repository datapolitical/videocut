import os, sys, json
import pathlib
import importlib.util

_cli_path = pathlib.Path(__file__).resolve().parents[1] / "videocut" / "cli.py"
_spec = importlib.util.spec_from_file_location("videocut.cli", _cli_path)
videocut_cli = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = videocut_cli
_spec.loader.exec_module(videocut_cli)

import videocut.core.transcription as transcribe_mod
import videocut.core.nicholson as nicholson_mod
import videocut.core.video_editing as video_editing


def test_pipeline_recognition(tmp_path, monkeypatch):
    json_file = tmp_path / "input.json"

    def fake_transcribe(video, hf_token, diarize):
        json_file.write_text(json.dumps({
            "segments": [
                {"speaker": "A", "text": "director doe you're recognized"},
                {"speaker": "B", "text": "hi"},
            ]
        }))

    monkeypatch.setattr(transcribe_mod, "transcribe", fake_transcribe)

    called = {}

    def fake_auto_mark(jf, out):
        called["auto_mark"] = True
        pathlib.Path(out).write_text("[]")

    monkeypatch.setattr(nicholson_mod, "auto_mark_nicholson", fake_auto_mark)

    def fake_generate(video, segs, out_dir):
        called["clips"] = True

    monkeypatch.setattr(video_editing, "generate_clips", fake_generate)
    monkeypatch.setattr(video_editing, "concatenate_clips", lambda a, b: called.setdefault("concat", True))

    def fake_map(jf):
        called["map"] = jf
        return {"Doe": "B"}

    monkeypatch.setattr(nicholson_mod, "map_recognized_auto", fake_map)

    monkeypatch.chdir(tmp_path)

    videocut_cli.pipeline(
        video="input.mp4",
        diarize=True,
        hf_token="tok",
        auto_nicholson=True,
    )

    assert called.get("map")
    assert json.loads(pathlib.Path("recognized_map.json").read_text()) == {"Doe": "B"}

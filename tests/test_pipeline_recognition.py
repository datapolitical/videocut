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
import videocut.core.chair as chair_mod
import videocut.core.annotation as annotation_mod
import videocut.core.clip_transcripts as clip_mod


def test_pipeline_recognition(tmp_path, monkeypatch):
    json_file = tmp_path / "input.json"

    def fake_transcribe(video, hf_token, diarize=True, speaker_db=None):
        json_file.write_text(json.dumps({
            "segments": [
                {"speaker": "A", "text": "director doe you're recognized"},
                {"speaker": "B", "text": "hi"},
            ]
        }))

    monkeypatch.setattr(transcribe_mod, "transcribe", fake_transcribe)

    called = {}

    def fake_identify(*args):
        called["identify"] = True
        pathlib.Path(args[2]).write_text("[]")

    monkeypatch.setattr(nicholson_mod, "identify_segments", fake_identify)

    def fake_generate(video, segs, out_dir):
        called["clips"] = True

    monkeypatch.setattr(video_editing, "generate_and_align", fake_generate)
    monkeypatch.setattr(video_editing, "concatenate_clips", lambda a, b: called.setdefault("concat", True))

    def fake_map(jf):
        called["map"] = jf
        return {"B": {"name": "Doe", "alternatives": []}}

    monkeypatch.setattr(nicholson_mod, "map_recognized_auto", fake_map)
    monkeypatch.setattr(chair_mod, "parse_roll_call", lambda jf: {})
    monkeypatch.setattr(annotation_mod, "annotate_segments", lambda a, b, c: called.setdefault("annotate", True))
    monkeypatch.setattr(clip_mod, "clip_transcripts", lambda a, b, c: called.setdefault("clips_txt", True))

    monkeypatch.chdir(tmp_path)

    videocut_cli.pipeline(
        video="input.mp4",
        hf_token="tok",
    )

    assert called.get("map")
    assert json.loads(pathlib.Path("recognized_map.json").read_text()) == {
        "B": {"name": "Doe", "alternatives": []}
    }

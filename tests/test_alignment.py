import json
import pathlib
from types import SimpleNamespace

import videocut.core.alignment as alignment


def test_align_with_transcript(tmp_path, monkeypatch):
    calls = {"ffmpeg": [], "load_align_model": False, "align": False, "wave": False}

    def fake_run(cmd, check):
        calls["ffmpeg"].append(cmd)
        pathlib.Path(cmd[-1]).write_bytes(b"")

    def fake_load_align_model(lang, device):
        calls["load_align_model"] = True
        return SimpleNamespace(), {}

    def fake_align(segs, am, meta, audio, device):
        calls["align"] = True
        return {"word_segments": [{"text": "hi", "start": 0.0, "end": 1.0}]}

    class FakeWave:
        def getnframes(self):
            return 16000

        def getframerate(self):
            return 16000

        def close(self):
            calls["wave"] = True

    def fake_wave_open(*args, **kwargs):
        return FakeWave()

    monkeypatch.setattr(alignment.subprocess, "run", fake_run)
    monkeypatch.setattr(alignment.whisperx, "load_align_model", fake_load_align_model)
    monkeypatch.setattr(alignment.whisperx, "align", fake_align)
    monkeypatch.setattr(alignment.wave, "open", fake_wave_open)

    transcript = tmp_path / "t.txt"
    transcript.write_text("hello")
    out_json = tmp_path / "out.json"

    alignment.align_with_transcript("video.mp4", str(transcript), str(out_json))

    assert calls["ffmpeg"]
    assert calls["load_align_model"]
    assert calls["align"]
    assert calls["wave"]
    assert json.loads(out_json.read_text()) == [{"text": "hi", "start": 0.0, "end": 1.0}]


def test_align_with_pdf_transcript(tmp_path, monkeypatch):
    calls = {"ffmpeg": [], "load_align_model": False, "align": False, "wave": False, "parse": False}

    def fake_parse_pdf(path):
        calls["parse"] = True
        return ["SPEAKER: hello"]

    def fake_run(cmd, check):
        calls["ffmpeg"].append(cmd)
        pathlib.Path(cmd[-1]).write_bytes(b"")

    def fake_load_align_model(lang, device):
        calls["load_align_model"] = True
        return SimpleNamespace(), {}

    def fake_align(segs, am, meta, audio, device):
        calls["align"] = True
        return {"word_segments": [{"text": "hi", "start": 0.0, "end": 1.0}]}

    class FakeWave:
        def getnframes(self):
            return 16000

        def getframerate(self):
            return 16000

        def close(self):
            calls["wave"] = True

    def fake_wave_open(*args, **kwargs):
        return FakeWave()

    monkeypatch.setattr(alignment.parse_pdf_text, "parse_pdf", fake_parse_pdf)
    monkeypatch.setattr(alignment.subprocess, "run", fake_run)
    monkeypatch.setattr(alignment.whisperx, "load_align_model", fake_load_align_model)
    monkeypatch.setattr(alignment.whisperx, "align", fake_align)
    monkeypatch.setattr(alignment.wave, "open", fake_wave_open)

    transcript = tmp_path / "t.pdf"
    transcript.write_bytes(b"%PDF-1.4")
    out_json = tmp_path / "out.json"

    alignment.align_with_transcript("video.mp4", str(transcript), str(out_json))

    assert calls["parse"]
    assert calls["ffmpeg"]
    assert calls["load_align_model"]
    assert calls["align"]
    assert calls["wave"]
    assert json.loads(out_json.read_text()) == [{"text": "hi", "start": 0.0, "end": 1.0}]

import os, sys, json
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import pathlib
import importlib.util
import videocut.core.nicholson as nicholson

_cli_path = pathlib.Path(__file__).resolve().parents[1] / "videocut" / "cli.py"
_spec = importlib.util.spec_from_file_location("videocut.cli", _cli_path)
videocut_cli = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = videocut_cli
_spec.loader.exec_module(videocut_cli)


def sample_data(tmp_path):
    diarized = tmp_path / "dia.json"
    diarized.write_text(json.dumps({
        "segments": [
            {"speaker": "A", "text": "hello secretary nicholson"},
            {"speaker": "B", "text": "other"},
            {"speaker": "B", "text": "mr doe reports"},
            {"speaker": "A", "text": "thanks"},
        ]
    }))
    mapping = tmp_path / "map.json"
    mapping.write_text(json.dumps({
        "Nicholson": ["secretary nicholson"],
        "Doe": ["mr doe"],
    }))
    return diarized, mapping


def test_map_speaker_by_phrases(tmp_path):
    diarized, mapping = sample_data(tmp_path)
    result = nicholson.map_speaker_by_phrases(str(diarized), json.loads(mapping.read_text()))
    assert result == {"Nicholson": "A", "Doe": "B"}


def test_identify_speakers_cli(tmp_path):
    diarized, mapping = sample_data(tmp_path)
    out = tmp_path / "ids.json"
    videocut_cli.identify_speakers(diarized_json=str(diarized), mapping=str(mapping), out=str(out))
    assert json.loads(out.read_text()) == {"Nicholson": "A", "Doe": "B"}


def sample_recog_data(tmp_path):
    diarized = tmp_path / "dia.json"
    diarized.write_text(json.dumps({
        "segments": [
            {"speaker": "X", "text": "call the roll"},
            {"speaker": "X", "text": "Director Doe"},
            {"speaker": "B", "text": "Present"},
            {"speaker": "X", "text": "Director Roe"},
            {"speaker": "C", "text": "Here"},
            {"speaker": "A", "text": "director doe you're recognized"},
            {"speaker": "B", "text": "hello"},
            {"speaker": "A", "text": "director roe you're recognized"},
            {"speaker": "C", "text": "thanks"},
        ]
    }))
    return diarized


def sample_recog_no_name(tmp_path):
    diarized = tmp_path / "dia2.json"
    diarized.write_text(json.dumps({
        "segments": [
            {"speaker": "X", "text": "call the roll"},
            {"speaker": "X", "text": "Director Smith"},
            {"speaker": "A", "text": "Present"},
            {"speaker": "X", "text": "Director Jones"},
            {"speaker": "B", "text": "Here"},
            {"speaker": "X", "text": "Let us proceed"},
            {"speaker": "X", "text": "Continuing"},
            {"speaker": "X", "text": "director smith."},
            {"speaker": "X", "text": "you're recognized"},
            {"speaker": "A", "text": "thanks"},
            {"speaker": "X", "text": "Director Jones"},
            {"speaker": "X", "text": "you are recognized"},
            {"speaker": "B", "text": "hello"},
        ]
    }))
    return diarized


def sample_recog_extra(tmp_path):
    diarized = tmp_path / "dia3.json"
    diarized.write_text(json.dumps({
        "segments": [
            {"speaker": "X", "text": "call the roll"},
            {"speaker": "X", "text": "Director Lee"},
            {"speaker": "A", "text": "Present"},
            {"speaker": "X", "text": "Ms. Kim"},
            {"speaker": "B", "text": "Here"},
            {"speaker": "X", "text": "Mr. Park"},
            {"speaker": "C", "text": "Present"},
            {"speaker": "X", "text": "Director Lee"},
            {"speaker": "A", "text": "hello"},
            {"speaker": "X", "text": "I yield the floor to Ms. Kim"},
            {"speaker": "B", "text": "thanks"},
            {"speaker": "X", "text": "call on Mr. Park"},
            {"speaker": "C", "text": "hi"},
        ]
    }))
    return diarized


def test_map_recognized_auto(tmp_path):
    diarized = sample_recog_data(tmp_path)
    ids = nicholson.map_recognized_auto(str(diarized))
    assert ids == {
        "B": {"name": "Doe", "alternatives": []},
        "C": {"name": "Roe", "alternatives": []},
    }


def test_identify_recognized_cli(tmp_path):
    diarized = sample_recog_data(tmp_path)
    out = tmp_path / "rec.json.out"
    videocut_cli.identify_recognized(diarized_json=str(diarized), out=str(out))
    assert json.loads(out.read_text()) == {
        "B": {"name": "Doe", "alternatives": []},
        "C": {"name": "Roe", "alternatives": []},
    }


def test_map_recognized_auto_context(tmp_path):
    diarized = sample_recog_no_name(tmp_path)
    ids = nicholson.map_recognized_auto(str(diarized))
    assert ids == {
        "A": {"name": "Smith", "alternatives": []},
        "B": {"name": "Jones", "alternatives": []},
    }


def test_map_recognized_auto_extra(tmp_path):
    diarized = sample_recog_extra(tmp_path)
    ids = nicholson.map_recognized_auto(str(diarized))
    assert ids == {
        "A": {"name": "Lee", "alternatives": []},
        "B": {"name": "Kim", "alternatives": []},
        "C": {"name": "Park", "alternatives": []},
    }


def test_add_speaker_labels(tmp_path):
    diarized, mapping = sample_data(tmp_path)
    ids = {"Nicholson": "A", "Doe": "B"}
    out = tmp_path / "lab.json"
    nicholson.add_speaker_labels(str(diarized), ids, str(out))
    data = json.loads(out.read_text())
    labels = [seg.get("label") for seg in data["segments"]]
    assert labels == ["Nicholson", "Doe", "Doe", "Nicholson"]


def test_apply_speaker_labels_cli(tmp_path):
    diarized, _ = sample_data(tmp_path)
    ids = {"Nicholson": "A", "Doe": "B"}
    map_file = tmp_path / "ids.json"
    map_file.write_text(json.dumps(ids))
    out = tmp_path / "lab_cli.json"
    videocut_cli.apply_speaker_labels(diarized_json=str(diarized), map_json=str(map_file), out=str(out))
    data = json.loads(out.read_text())
    assert data["segments"][0]["label"] == "Nicholson"
    assert data["segments"][1]["label"] == "Doe"

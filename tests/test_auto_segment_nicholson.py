import os, sys, json
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import pytest
from videocut.core import nicholson
from videocut.core.nicholson import (
    find_nicholson_speaker,
    start_score,
    end_score,
)


def test_find_nicholson_speaker_none():
    segments = [
        {"speaker": "A", "text": "hello"},
        {"speaker": "B", "text": "how are you"},
        {"speaker": "A", "text": "thanks"},
    ]
    assert find_nicholson_speaker(segments) is None


def test_segment_ends_on_new_director(tmp_path):
    diarized = tmp_path / "dia.json"
    diarized.write_text(json.dumps({
        "segments": [
            {"start": 0.0, "end": 0.5, "speaker": "C", "text": "I have secretary Nicholson"},
            {"start": 0.5, "end": 1.0, "speaker": "N", "text": "comment"},
            {"start": 1.1, "end": 1.4, "speaker": "C", "text": "Okay, Ms. Smith"},
            {"start": 1.5, "end": 2.0, "speaker": "S", "text": "other"},
        ]
    }))
    out = tmp_path / "keep.json"

    nicholson.segment_nicholson(str(diarized), str(out))

    segs = json.loads(out.read_text())
    assert len(segs) == 1
    assert segs[0]["end"] == pytest.approx(1.5)


def test_scoring_helpers():
    assert start_score("I have Secretary Nicholson") >= 0.8
    assert end_score("Thank you, Director") >= 0.6


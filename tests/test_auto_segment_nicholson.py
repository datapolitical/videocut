import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import pytest
from auto_segment_nicholson import find_nicholson_speaker


def test_find_nicholson_speaker_none():
    segments = [
        {"speaker": "A", "text": "hello"},
        {"speaker": "B", "text": "how are you"},
        {"speaker": "A", "text": "thanks"},
    ]
    assert find_nicholson_speaker(segments) is None


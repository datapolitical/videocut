import os, sys, json
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from videocut.core import chair


def sample_roll_call(tmp_path):
    diarized = tmp_path / "dia.json"
    diarized.write_text(json.dumps({
        "segments": [
            {"speaker": "A", "text": "welcome"},
            {"speaker": "A", "text": "I will now call the roll"},
            {"speaker": "A", "text": "Director Doe"},
            {"speaker": "B", "text": "Present"},
            {"speaker": "A", "text": "Director Roe"},
            {"speaker": "C", "text": "Here"},
        ]
    }))
    return diarized


def sample_rollcall_variation(tmp_path):
    diarized = tmp_path / "dia_var.json"
    diarized.write_text(json.dumps({
        "segments": [
            {"speaker": "A", "text": "welcome"},
            {"speaker": "A", "text": "Let's do a rollcall"},
            {"speaker": "A", "text": "Director Doe"},
            {"speaker": "B", "text": "Present"},
        ]
    }))
    return diarized


def sample_rollcall_no_phrase(tmp_path):
    diarized = tmp_path / "dia_no_phrase.json"
    diarized.write_text(json.dumps({
        "segments": [
            {"speaker": "A", "text": "welcome"},
            {"speaker": "A", "text": "Director Doe"},
            {"speaker": "B", "text": "Present"},
            {"speaker": "A", "text": "Director Roe"},
            {"speaker": "C", "text": "Here"},
        ]
    }))
    return diarized


def sample_motion_phrase(tmp_path):
    diarized = tmp_path / "dia_motion.json"
    diarized.write_text(json.dumps({
        "segments": [
            {"speaker": "X", "text": "Okay, moving on"},
            {"speaker": "X", "text": "Do I have a motion?"},
        ]
    }))
    return diarized


def sample_other_phrases(tmp_path):
    diarized = tmp_path / "dia_other.json"
    diarized.write_text(json.dumps({
        "segments": [
            {"speaker": "A", "text": "Moving on"},
            {"speaker": "B", "text": "Hello"},
            {"speaker": "A", "text": "Any other matters?"},
        ]
    }))
    return diarized


def sample_weighted(tmp_path):
    diarized = tmp_path / "dia_weight.json"
    diarized.write_text(json.dumps({
        "segments": [
            {"speaker": "A", "text": "Moving on"},
            {"speaker": "B", "text": "Do I have a motion?"},
        ]
    }))
    return diarized


def sample_roll_call_srt(tmp_path):
    srt = tmp_path / "dia.srt"
    srt.write_text(
        """1
00:00:00,000 --> 00:00:01,000
[SPEAKER_1]: welcome

2
00:00:01,000 --> 00:00:02,000
[SPEAKER_1]: I will now call the roll

3
00:00:02,000 --> 00:00:03,000
[SPEAKER_1]: Director Doe

4
00:00:03,000 --> 00:00:04,000
[SPEAKER_2]: Present
"""
    )
    return srt


def test_identify_chair(tmp_path):
    diarized = sample_roll_call(tmp_path)
    assert chair.identify_chair(str(diarized)) == "A"


def test_parse_roll_call(tmp_path):
    diarized = sample_roll_call(tmp_path)
    votes = chair.parse_roll_call(str(diarized))
    assert votes == {"Doe": "B", "Roe": "C"}


def test_identify_chair_srt(tmp_path):
    srt_file = sample_roll_call_srt(tmp_path)
    assert chair.identify_chair_srt(str(srt_file)) == "SPEAKER_1"


def test_identify_chair_variation(tmp_path):
    diarized = sample_rollcall_variation(tmp_path)
    assert chair.identify_chair(str(diarized)) == "A"


def test_identify_chair_no_phrase(tmp_path):
    diarized = sample_rollcall_no_phrase(tmp_path)
    assert chair.identify_chair(str(diarized)) == "A"
    votes = chair.parse_roll_call(str(diarized))
    assert votes == {"Doe": "B", "Roe": "C"}


def test_identify_chair_motion(tmp_path):
    diarized = sample_motion_phrase(tmp_path)
    assert chair.identify_chair(str(diarized)) == "X"


def test_identify_chair_other_phrases(tmp_path):
    diarized = sample_other_phrases(tmp_path)
    assert chair.identify_chair(str(diarized)) == "A"


def test_identify_chair_weighted(tmp_path):
    diarized = sample_weighted(tmp_path)
    # motion phrase has higher weight than moving on
    assert chair.identify_chair(str(diarized)) == "B"


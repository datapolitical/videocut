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


def test_identify_chair(tmp_path):
    diarized = sample_roll_call(tmp_path)
    assert chair.identify_chair(str(diarized)) == "A"


def test_parse_roll_call(tmp_path):
    diarized = sample_roll_call(tmp_path)
    votes = chair.parse_roll_call(str(diarized))
    assert votes == {"Doe": "B", "Roe": "C"}

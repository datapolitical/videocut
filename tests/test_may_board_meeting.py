import json
from pathlib import Path

from videocut.core import nicholson


def _iou(a, b):
    start = max(a["start"], b["start"])
    end = min(a["end"], b["end"])
    if end <= start:
        return 0.0
    inter = end - start
    union = (a["end"] - a["start"]) + (b["end"] - b["start"]) - inter
    return inter / union


def _score_segments(expected, result):
    scores = []
    for e in expected:
        best = 0.0
        for r in result:
            s = _iou(e, r)
            if s > best:
                best = s
        scores.append(best)
    overall = sum(scores) / len(scores) if scores else 0.0
    return scores, overall


def test_may_board_meeting_segments(tmp_path):
    base = Path("videos/May_Board_Meeting")
    input_json = base / "May_Board_Meeting.json"
    expected_json = base / "segments_to_keep.json"
    recognized_map = base / "recognized_map.json"

    out_json = tmp_path / "segments.json"

    nicholson.segment_nicholson(
        str(input_json),
        str(out_json),
        recognized_map=str(recognized_map),
    )

    result = json.loads(out_json.read_text())
    expected = json.loads(expected_json.read_text())

    scores, overall = _score_segments(expected, result)
    (tmp_path / "evaluation.json").write_text(
        json.dumps({"scores": scores, "overall": overall}, indent=2)
    )
    print(f"Overall score: {overall:.2f}")
    if overall <= 0.9:
        low = [i for i, s in enumerate(scores) if s < 0.9]
        print("Low scoring segments:", low)
    assert overall > 0.9, f"Overall segmentation score {overall:.2f} below 0.9"

# Available Tests

- `test_core.py`: verifies transcription helper functions and clip generation commands.
- `test_speaker_mapping.py`: checks speaker mapping utilities and related CLI commands.
- `test_chair_rollcall.py`: exercises chair identification and roll call parsing.
- `test_segmentation_utils.py`: covers segmentation helper functions including text/JSON round trips.
- `test_auto_segment_nicholson.py`: validates Nicholson segmentation heuristics.
- `test_may_board_meeting.py::test_may_board_meeting_segments`: evaluates segmentation accuracy on the May_Board_Meeting example.
- **Segmentation test**: run `videocut identify-recognized` and `videocut identify-segments` on `videos/example/example.mp4`,
  attempt segmentation with an LLM, and compare the results. Logs written to `debug.log`.

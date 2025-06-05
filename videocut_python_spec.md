# 🛠️ VideoCut Python Reimplementation Specification

This document outlines a modern Python-based reimplementation plan for the VideoCut pipeline, integrating transcription, diarization, clip generation, and CLI utilities.

---

## 1. Language & Tools

- **Primary Language:** Python 3.10+
- **Package Manager:** Poetry or pip with virtualenv
- **Video Processing:** FFmpeg (invoked via shell or `ffmpeg-python`)
- **Transcription Engine:** `faster-whisper`
- **Diarization Engine:** `pyannote-audio`
- **CLI Framework:** `Typer`
- **Testing Framework:** `pytest`
- **Optional Orchestration:** `Make`, `invoke`, or `Prefect`

---

## 2. Modules Overview

### `core/transcription.py`
- Uses `faster-whisper` to transcribe a video
- Outputs: `<input>.json`, `markup_guide.txt`
- Automatically selects compute mode (CPU/GPU)

### `core/diarization.py`
- Uses `pyannote-audio` to perform speaker diarization
- Maps diarization results to transcript segments
- Output: enriched JSON transcript with speaker labels

### `core/segmentation.py`
- Converts JSON → editable JSON / TSV
- Extracts segments with `keep` flag
- Detects `{START}` / `{END}` markers from markup

### `core/nicholson.py`
- Heuristics for detecting Secretary Nicholson segments
- Uses segment text + diarization speaker ID if available
- Groups segments, adds context

### `core/video_editing.py`
- Uses FFmpeg to:
  - Cut and fade clips
  - Pad to 1280×720, 30fps
  - Concatenate with white flash

### `core/utils.py`
- JSON/TSV parsing, logging, file utilities

---

## 3. CLI Commands (`cli/`)

### `videocut transcribe <video_path>`
- Transcribe video using `faster-whisper`

### `videocut diarize <video_path>`
- Extract audio and perform diarization
- Save as `diarization.json`

### `videocut align diarization.json transcript.json`
- Match transcript segments with speakers

### `videocut mark segments_edit.json`
- Manual or auto segment marking

### `videocut cut segments_to_keep.json`
- Generate clips from source video

### `videocut concat clips_dir/`
- Join clips with fades and flashes

### `videocut pipeline <video_path> [--auto-nicholson]`
- Full pipeline from raw video to final output

---

## 4. Output Artifacts

- `<input>.json` — transcript
- `markup_guide.txt` — readable format
- `segments_edit.json`, `input.tsv` — manual editing formats
- `segments_to_keep.json` — final clip boundaries
- `clips/clip_XXX.mp4` — generated clips
- `final_video.mp4` — output video
- `markup_with_markers.txt`, `clip_transcripts.txt` — optional utilities

---

## 5. Notes on Diarization Integration

- `pyannote-audio` is used separately from transcription
- Transcript segments are matched to diarization speaker turns by timestamp overlap
- Diarization requires a Hugging Face token

---

## 6. Project Structure

```
videocut/
├── core/
│   ├── transcription.py
│   ├── diarization.py
│   ├── segmentation.py
│   ├── video_editing.py
│   ├── nicholson.py
│   └── utils.py
├── cli/
│   ├── transcribe.py
│   ├── diarize.py
│   ├── cut.py
│   ├── concat.py
│   └── pipeline.py
├── tests/
├── examples/
├── videos/
├── pyproject.toml
└── README.md
```

---

## 7. Testing Plan

- Unit tests for each module
- Integration tests for full pipeline with sample data
- CLI output verification

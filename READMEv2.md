# VideoCut

VideoCut turns recorded board meetings into polished, shareable clips with minimal effort. Provide a video file and its transcript, and the `videocut` CLI will:

1. **Align** the transcript to the audio.  
2. **Detect** and group Secretary Nicholson’s remarks.  
3. **Cut** numbered clips ready for distribution.

## Requirements

- **Python 3.11 or higher**  
- **FFmpeg** available on your `PATH`  
- **WhisperX** and its dependencies  
- `HF_TOKEN` environment variable — required for WhisperX speaker diarization

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Typical Workflow

| Step | Command | Output |
|------|---------|--------|
| 1 | `videocut transcribe May_Board_Meeting.mp4 transcript.pdf` | `May_Board_Meeting.json` |
| 2 | `videocut identify-segments May_Board_Meeting.json` | `segments.txt` (tab‑indented) |
| 2a *(optional)* | *Edit* `segments.txt` to trim or reorder segments | — |
| 3 | `videocut generate-clips May_Board_Meeting.mp4 segments.txt` | Clips and `timestamps.json` |
| 4 | `videocut concatenate` | `final_video.mp4` |

`generate-clips` buffers each segment, re-aligns its text and trims to the
spoken words. Per-clip alignment data is written as `clip_###_aligned.json` and
`timestamps.json` records the original versus aligned timings.

## Project Layout

- `videocut/cli.py` — Typer command‑line interface  
- `videocut/core/` — modular helpers  
- `videos/` — example data for testing

## PDF Transcript Cleanup

Replace ASR text with an official PDF transcript:

```bash
videocut pdf-transcript \
    videos/May_Board_Meeting/May_Board_Meeting.json \
    videos/May_Board_Meeting/transcript.pdf
```

If you’re using the integrated ASR pipeline, pass `--pdf transcript.pdf` to `videocut transcribe` or `videocut pipeline` to include this step automatically. Using the cleaned PDF text improves the accuracy of subsequent segmentation.

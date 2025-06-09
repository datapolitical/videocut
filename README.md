# VideoCut

VideoCut provides a streamlined video editing pipeline powered by WhisperX. The `videocut` command runs every step needed to process a board meeting recording.

## Requirements
- Python 3.11+
- [FFmpeg](https://ffmpeg.org/) on your `PATH`
- [WhisperX](https://github.com/m-bain/whisperX) and its dependencies
- `HF_TOKEN` environment variable for speaker diarization

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Workflow
1. **Transcribe** – `videocut transcribe input.mp4 --diarize --hf_token $HF_TOKEN`
   produces `input.json` and `markup_guide.txt` with diarized speaker labels.
2. **Identify recognized speakers** – `videocut identify-recognized input.json`
   detects the chair from the roll call and writes `recognized_map.json` and
   `roll_call_map.json`.
3. **Identify segments** – `videocut identify-segments input.json` creates
   `segments_to_keep.json` grouping Secretary Nicholson's remarks.
4. **Generate clips** – `videocut generate-clips input.mp4` cuts clips to `clips/`.
5. **Concatenate** – `videocut concatenate` joins clips into `final_video.mp4`.
6. **Annotate markup** – `videocut annotate-markup` writes `markup_with_markers.txt`.
7. **Clip transcripts** – `videocut clip-transcripts` produces `clip_transcripts.txt`.

All of these steps run automatically with:
```bash
videocut pipeline input.mp4 --hf_token $HF_TOKEN
```

## Package layout
- `videocut/cli.py` – Typer command line interface
- `videocut/core/` – modular helpers
- `videos/` – example data used for testing
- `board_members.txt` – official director names

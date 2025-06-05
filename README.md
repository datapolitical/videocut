# VideoCut

VideoCut provides a small video editing pipeline driven by WhisperX transcripts.  Each step of the process is broken out into a script under `scripts/` and backed by small modules for re-use.

## Requirements

- Python 3.11+
- [FFmpeg](https://ffmpeg.org/) available on your `PATH`
- [WhisperX](https://github.com/m-bain/whisperX) and its dependencies (installed via `requirements.txt`)

## Setup

Create a virtual environment and install packages:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Speaker diarization requires a Hugging Face access token.  Set `HF_TOKEN` in your environment or in a `.env` file:

```bash
HF_TOKEN=your_hf_token_here
```

## Workflow

1. **Transcribe** – `scripts/transcribe_step.py` runs WhisperX and produces `markup_guide.txt` and the original JSON file.
2. **Prepare for editing** – use `scripts/json_to_tsv_step.py` to create `input.tsv` or `scripts/json_to_editable_step.py` for `segments_edit.json`.
3. **Identify clips** – after marking segments to keep, run one of
   `scripts/identify_clips_step.py`, `scripts/identify_clips_json_step.py` or
   `scripts/extract_marked_step.py` to create `segments_to_keep.json`.
4. **Auto-select Nicholson segments (optional)** – `scripts/auto_mark_nicholson_step.py` examines a diarized JSON file and builds the JSON list for you.
5. **Generate clips** – `scripts/generate_clips_step.py` cuts clips from the input video into a `clips/` directory.
6. **Concatenate** – `scripts/concatenate_clips_step.py` stitches the clips together with white flashes between each.

All of these steps can be executed sequentially with `scripts/run_pipeline.py --all`.

### Example commands

```bash
# Transcription with diarization
python3 scripts/transcribe_step.py --input meeting.mp4 --diarize --hf_token $HF_TOKEN

# Convert JSON to TSV for spreadsheet editing
python3 scripts/json_to_tsv_step.py meeting.json --out input.tsv
# (edit input.tsv to mark rows to keep)

# Generate the list of segments
python3 scripts/identify_clips_step.py --tsv input.tsv

# Cut clips and assemble the final video
python3 scripts/generate_clips_step.py --input meeting.mp4 --json segments_to_keep.json
python3 scripts/concatenate_clips_step.py --clips_dir clips --out final.mp4
```

## Package layout

- `transcribe.py` – wrapper around WhisperX used by multiple scripts
- `clip_utils.py` – helpers for converting transcripts, identifying clips, cutting and concatenating video
- `scripts/` – single-purpose step scripts (see above) including `run_pipeline.py`
- `process_video.py` and `lightweight_process.py` – monolithic CLIs combining all steps
- `videos/` – example data used for testing the pipeline

WhisperX and FFmpeg must be installed separately.  Once those are available, the scripts above can be combined or run individually to automate cutting long meeting videos into polished clips.

# VideoCut

VideoCut provides a small video editing pipeline driven by WhisperX transcripts.
Each step of the process is available as an executable module under
`videocut/cli/steps/` and backed by small reusable helpers.

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

1. **Transcribe** – `videocut/cli/steps/transcribe_step.py` runs WhisperX and
   produces `markup_guide.txt` and the original JSON file.
2. **Prepare for editing** – use `videocut/cli/steps/json_to_editable_step.py` to
   create `segments_edit.json` (or `json_to_tsv_step.py` for spreadsheet TSV).
3. **Identify clips** – after marking segments to keep, run one of
   `videocut/cli/steps/identify_clips_json_step.py` or
   `videocut/cli/steps/extract_marked_step.py` to create `segments_to_keep.json`.
4. **Auto-select Nicholson segments (optional)** –
   `videocut/cli/steps/auto_mark_nicholson_step.py` examines a diarized JSON file
   and builds the JSON list for you.
5. **Generate clips** – `videocut/cli/steps/generate_clips_step.py` cuts clips
   from the input video into a `clips/` directory.
6. **Concatenate** – `videocut/cli/steps/concatenate_clips_step.py` stitches the
   clips together with white flashes between each.

All of these steps can be executed sequentially with
`videocut/cli/steps/run_pipeline.py --all`.

The `v2/pipeline.py` script offers an alternative audio-first workflow. It
downloads only the audio track for transcription and later redownloads just the
needed video segments using `yt-dlp --download-sections`.

### Example commands

```bash
# Transcription with diarization
python3 videocut/cli/steps/transcribe_step.py --input meeting.mp4 --diarize --hf_token $HF_TOKEN

# Convert JSON to TSV for spreadsheet editing
python3 videocut/cli/steps/json_to_tsv_step.py meeting.json --out input.tsv
# (edit input.tsv to mark rows to keep)

# Generate the list of segments
python3 videocut/cli/steps/identify_clips_json_step.py --json segments_edit.json

# Cut clips and assemble the final video
python3 videocut/cli/steps/generate_clips_step.py --input meeting.mp4 --json segments_to_keep.json
python3 videocut/cli/steps/concatenate_clips_step.py --clips_dir clips --out final.mp4

# Or run the audio-first pipeline
python3 v2/pipeline.py --url "https://youtu.be/video" --download-audio --transcribe --extract-marked --generate-clips --concatenate
```

## Package layout

- `videocut/core/` – shared helpers for transcription and clip generation
- `videocut/cli/steps/` – small executable modules for each pipeline step
- `v2/` – audio-first pipeline script
- `process_video.py` and `lightweight_process.py` – legacy monolithic CLIs
- `videos/` – example data used for testing the pipeline

WhisperX and FFmpeg must be installed separately. Once those are
available, the scripts above can be combined or run individually to
automate cutting long meeting videos into polished clips.

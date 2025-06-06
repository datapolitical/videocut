# VideoCut

VideoCut provides a small video editing pipeline driven by WhisperX transcripts.  The project now exposes a single `videocut` command powered by **Typer** for easy usage.  All functionality can still be invoked step-by-step or via a one-shot pipeline command.

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
pip install -e .
```

If you already have transcripts and want to skip WhisperX's heavy install,
install only the lightweight dependencies instead:

```bash
pip install -r no_transcribe_requirements.txt
```

Verify the CLI loads properly:

```bash
videocut --help
```

Speaker diarization requires a Hugging Face access token.  Set `HF_TOKEN` in your environment or in a `.env` file:

```bash
HF_TOKEN=your_hf_token_here
```

## Workflow

1. **Transcribe with diarization** – `videocut transcribe input.mp4 --diarize --hf_token $HF_TOKEN` runs WhisperX and produces `markup_guide.txt` and `input.json` with speaker labels.
   Provide `--speaker-db speakers.json` to map diarized IDs to real names.
2. **Auto-mark Nicholson** – `videocut auto-mark-nicholson input.json` generates
   `segments_to_keep.json` grouping Nicholson's remarks into coherent segments.
3. **Review and edit** – optionally run `videocut json-to-editable segments_to_keep.json` and modify the JSON to fine‑tune the clips.
4. **Generate clips** – `videocut generate-clips input.mp4` cuts clips into a `clips/` directory.
5. **Concatenate** – `videocut concatenate` stitches the clips together with white flashes.
6. **Annotate markup** – `videocut annotate-markup` creates `markup_with_markers.txt` showing kept segments in context.
7. **Clip transcripts** – `videocut clip-transcripts` summarizes the transcript lines for each long clip.

All of these steps can be executed sequentially with `videocut pipeline input.mp4 --diarize --hf_token $HF_TOKEN` which auto‑marks Nicholson by default.

### Example commands

```bash
# Build embeddings from known speakers
videocut build-speaker-db samples/ --out speakers.json

# Transcription with diarization
videocut transcribe meeting.mp4 --diarize --hf_token $HF_TOKEN --speaker-db speakers.json

# Auto-mark Nicholson segments into grouped clips
videocut auto-mark-nicholson meeting.json

# (Optional) tweak the segments
videocut json-to-editable segments_to_keep.json --out segments_edit.json
# ...edit segments_edit.json as desired...

# Cut clips and assemble the final video
videocut generate-clips meeting.mp4 --segs segments_to_keep.json
videocut concatenate --clips_dir clips --out final.mp4
videocut annotate-markup
videocut clip-transcripts

# Map speakers after transcription
videocut map-speakers meeting.mp4 meeting.json --db speakers.json
```

## Package layout

- `videocut/cli.py` – Typer command line interface
- `videocut/core/` – modular helpers (`transcription.py`, `segmentation.py`, `video_editing.py`, `nicholson.py`, `annotation.py`, `clip_transcripts.py`, `speaker_mapping.py`)
- `videos/` – example data used for testing the pipeline

WhisperX and FFmpeg must be installed separately.  Once those are available, the `videocut` command can automate cutting long meeting videos into polished clips.

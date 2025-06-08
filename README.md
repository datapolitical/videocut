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
2. **Identify segments** – `videocut identify-segments input.json` generates
   `segments_to_keep.json` grouping Nicholson's remarks into coherent segments using recognized speaker IDs.
   The script also cross-checks with text heuristics and warns if the methods disagree.
<<<<   A list of official board member names is provided in `board_members.txt` so replies
   from non‑directors can be captured when extending Nicholson's segments.
   Run `videocut apply-name-map` to replace `SPEAKER_xx` tokens in the JSON with
   mapped names and `videocut prune-segments` to drop trivial clips.
>>>>>>>+main
=
   A l   A list of official board member names in `board_members.txt` lets the tool
   include staff answers when Nicholson asks a question.  Speaker IDs are now
   replaced with recognized names automatically and `videocut prune-segments`
   can drop trivial clips.
>>>>>>>-fup1ec-codex/fi
eview and edit** – optionally run `videocut json-to-editable segments_to_keep.json` and modify the JSON to fine‑tune the clips.
4. **Generate clips** – `videocut generate-clips input.mp4` cuts clips into a `clips/` directory.
5. **Concatenate** – `videocut concatenate` stitches the clips together with white flashes.
6. **Annotate markup** – `videocut annotate-markup` creates `markup_with_markers.txt` showing kept segments in context.
7. **Clip transcripts** – `videocut clip-transcripts` summarizes the transcript lines for each long clip.

All of these steps can be executed sequentially with `videocut pipeline input.mp4 --diarize --hf_token $HF_TOKEN` which auto‑marks Nicholson by default.

### Automatic speaker identification

When diarization is enabled, VideoCut scans the transcript for recognition cues
such as "Director Doe you're recognized" or simply "You're recognized" when the
chair has just mentioned a name. Short lines that end with just "Director Name" or phrases like "yield the floor to Director Name" are also detected. The chair is identified from the roll call first, then these cues map each diarized speaker ID to its most likely name with any alternatives. Results are written to `recognized_map.json`.
`identify-recognized` command can be run manually if needed:

```bash
videocut identify-recognized input.json
```

The pipeline command performs this detection automatically and prints a warning
if no recognition cues are found.

For multiple people you can supply a phrase map to `identify-speakers`:

```bash
videocut identify-speakers input.json phrase_map.json
```

The resulting `speaker_map.json` can then be applied back to the transcript:

```bash

videocut apply-speaker-labels input.json speaker_map.json --out labeled.json
```

### Chair identification and roll call

When a meeting transcript includes a roll call vote, the speaker who announces
"call the roll" is treated as the chair. Names read during the roll call are
paired with the voices that respond "present" or "here" so diarization can be
validated. The mapping of names to speaker labels can be extracted with:

```bash
videocut identify-chair input.json
```

### Example commands

```bash
# Build embeddings from known speakers
videocut build-speaker-db samples/ --out speakers.json

# Transcription with diarization
videocut transcribe meeting.mp4 --diarize --hf_token $HF_TOKEN --speaker-db speakers.json

# Identify Nicholson segments into grouped clips
videocut identify-segments meeting.json

# (Optional) tweak the segments
videocut json-to-editable segments_to_keep.json --out segments_edit.json
# ...edit segments_edit.json as desired...

# Cut clips and assemble the final video
videocut generate-clips meeting.mp4 --segs segments_to_keep.json
videocut concatenate --clips_dir clips --out final.mp4
videocut annotate-markup
videocut clip-transcripts

# Repla# Replace SPEAKER IDs with names and prune trivial segments
videocut apply-name-map segments_to_keep.json recognized_map.json
>>>>>>>+main
ial segm# Prune trivial segments
>>>>>>>-fup1ec-codex/fi
nts segments_to_keep.json

# List recognized directors
videocut recognized-directors recognized_map.json board_members.txt

# Map speakers after transcription
videocut map-speakers meeting.mp4 meeting.json --db speakers.json
```

## Package layout

- `videocut/cli.py` – Typer command line interface
- `videocut/core/` – modular helpers (`transcription.py`, `segmentation.py`, `video_editing.py`, `nicholson.py`, `annotation.py`, `clip_transcripts.py`, `speaker_mapping.py`)
- `videos/` – example data used for testing the pipeline
- `board_members.txt` – official names used when matching directors

WhisperX and FFmpeg must be installed separately.  Once those are available, the `videocut` command can automate cutting long meeting videos into polished clips.
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
2. **Identify segments** – `videocut identify-segments input.json` generates
   `segments_to_keep.json` grouping Nicholson's remarks into coherent segments using recognized speaker IDs.
   The script also cross-checks with text heuristics and warns if the methods disagree.
<<<<   A list of official board member names is provided in `board_members.txt` so replies
   from non‑directors can be captured when extending Nicholson's segments.
   Run `videocut apply-name-map` to replace `SPEAKER_xx` tokens in the JSON with
   mapped names and `videocut prune-segments` to drop trivial clips.
>>>>>>>+main
=
   A l   A list of official board member names in `board_members.txt` lets the tool
   include staff answers when Nicholson asks a question.  Speaker IDs are now
   replaced with recognized names automatically and `videocut prune-segments`
   can drop trivial clips.
>>>>>>>-fup1ec-codex/fi
eview and edit** – optionally run `videocut json-to-editable segments_to_keep.json` and modify the JSON to fine‑tune the clips.
4. **Generate clips** – `videocut generate-clips input.mp4` cuts clips into a `clips/` directory.
5. **Concatenate** – `videocut concatenate` stitches the clips together with white flashes.
6. **Annotate markup** – `videocut annotate-markup` creates `markup_with_markers.txt` showing kept segments in context.
7. **Clip transcripts** – `videocut clip-transcripts` summarizes the transcript lines for each long clip.

All of these steps can be executed sequentially with `videocut pipeline input.mp4 --diarize --hf_token $HF_TOKEN` which auto‑marks Nicholson by default.

### Automatic speaker identification

When diarization is enabled, VideoCut scans the transcript for recognition cues
such as "Director Doe you're recognized" or simply "You're recognized" when the
chair has just mentioned a name. Short lines that end with just "Director Name" or phrases like "yield the floor to Director Name" are also detected. The chair is identified from the roll call first, then these cues map each diarized speaker ID to its most likely name with any alternatives. Results are written to `recognized_map.json`.
`identify-recognized` command can be run manually if needed:

```bash
videocut identify-recognized input.json
```

The pipeline command performs this detection automatically and prints a warning
if no recognition cues are found.

For multiple people you can supply a phrase map to `identify-speakers`:

```bash
videocut identify-speakers input.json phrase_map.json
```

The resulting `speaker_map.json` can then be applied back to the transcript:

```bash

videocut apply-speaker-labels input.json speaker_map.json --out labeled.json
```

### Chair identification and roll call

When a meeting transcript includes a roll call vote, the speaker who announces
"call the roll" is treated as the chair. Names read during the roll call are
paired with the voices that respond "present" or "here" so diarization can be
validated. The mapping of names to speaker labels can be extracted with:

```bash
videocut identify-chair input.json
```

### Example commands

```bash
# Build embeddings from known speakers
videocut build-speaker-db samples/ --out speakers.json

# Transcription with diarization
videocut transcribe meeting.mp4 --diarize --hf_token $HF_TOKEN --speaker-db speakers.json

# Identify Nicholson segments into grouped clips
videocut identify-segments meeting.json

# (Optional) tweak the segments
videocut json-to-editable segments_to_keep.json --out segments_edit.json
# ...edit segments_edit.json as desired...

# Cut clips and assemble the final video
videocut generate-clips meeting.mp4 --segs segments_to_keep.json
videocut concatenate --clips_dir clips --out final.mp4
videocut annotate-markup
videocut clip-transcripts

<<<<<<< main
# Repla# Replace SPEAKER IDs with names and prune trivial segments
videocut apply-name-map segments_to_keep.json recognized_map.json
>>>>>>>+main
ial segm# Prune trivial segments
>>>>>>>-fup1ec-codex/fi
nts segments_to_keep.json

# List recognized directors
videocut recognized-directors recognized_map.json board_members.txt

# Map speakers after transcription
videocut map-speakers meeting.mp4 meeting.json --db speakers.json
```

## Package layout

- `videocut/cli.py` – Typer command line interface
- `videocut/core/` – modular helpers (`transcription.py`, `segmentation.py`, `video_editing.py`, `nicholson.py`, `annotation.py`, `clip_transcripts.py`, `speaker_mapping.py`)
- `videos/` – example data used for testing the pipeline
- `board_members.txt` – official names used when matching directors

WhisperX and FFmpeg must be installed separately.  Once those are available, the `videocut` command can automate cutting long meeting videos into polished clips.

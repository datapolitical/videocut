# VideoCut Pipeline

This repository provides a set of Python scripts for transcribing a meeting video,
marking timestamps to keep, and producing a final stitched video of clips.

Two approaches are available:

* **Regular pipeline** – run one of the root-level Python files directly.
* **Step pipeline** – execute the modular scripts in `scripts/` for each phase.

The examples under `videos/` illustrate files created by the scripts.

## Setup

1. Install Python 3.11+.
2. Install required packages:

   ```bash
   pip install -r requirements.txt
   ```

   If you already have the WhisperX dependencies installed and do not need
   to run transcription, use `no_transcribe_requirements.txt` instead.

3. Create a `.env` file containing your `HF_TOKEN` from Hugging Face. The
   pipeline expects diarized JSON files, so transcription normally runs with
   `--diarize`. You may skip the token only if you already have the diarized
   JSON produced elsewhere.

## Full workflow

These are the required steps to turn `input.mp4` into a single concatenated
video of selected segments. Each step shows how to run it with the regular
`process_video.py` script and the equivalent file in `scripts/`.

1. **Transcribe with diarization**

   ```bash
   python3 process_video.py --input input.mp4 --transcribe --diarize \
       --hf_token YOUR_TOKEN
   # or
   python3 scripts/transcribe_step.py --input input.mp4 --hf_token YOUR_TOKEN \
       --diarize
   ```

   Generates `markup_guide.txt` and `input.json` containing timestamps and
   speaker labels.

2. **Convert JSON for editing**

```bash
python3 scripts/json_to_editable_step.py input.json
```

This creates `segments_edit.json` with `keep` flags and context fields for each
segment.

3. **Mark segments to keep**

   - Edit `segments_edit.json` and run `scripts/identify_clips_json_step.py`.
   - You can also mark ranges directly in `markup_guide.txt` and run
     `scripts/extract_marked_step.py`.

   All approaches generate `segments_to_keep.json`.

4. **Generate polished clips**

   ```bash
   python3 process_video.py --input input.mp4 --generate-clips
   # or
   python3 scripts/generate_clips_step.py --input input.mp4 \
       --json segments_to_keep.json
   ```

   Creates `clips/clip_###.mp4` files with fades and padding.

5. **Concatenate to the final video**

   ```bash
   python3 process_video.py --concatenate
   # or
   python3 scripts/concatenate_clips_step.py --clips_dir clips \
       --out final_video.mp4
   ```

   Produces `final_video.mp4` with white flashes between clips.

## Regular pipeline

### `process_video.py`

One script handles all phases. The most common usage is:

```bash
python3 process_video.py --input input.mp4 --transcribe --identify-clips-json \
    --generate-clips --concatenate
```

Flags control which steps run:

- `--transcribe` – run WhisperX and create `markup_guide.txt`.
- `--diarize` – include speaker diarization.
- `--identify-clips-json` – parse `segments_edit.json` to `segments_to_keep.json`.
- `--extract-marked` – instead parse `markup_guide.txt` with START/END markers.
- `--generate-clips` – cut clips from `segments_to_keep.json`.
- `--concatenate` – stitch clips to `final_video.mp4`.

### `lightweight_process.py`

A lighter wrapper around the same functionality that imports from
`transcribe.py` and `clip_utils.py`. Command line flags mirror those
of `process_video.py`.

### Other root files

- `transcribe.py` – helper called by the other scripts. You rarely run this
  directly.
- `clip_utils.py` – library of common clip-processing functions.
- `auto_segment_nicholson.py` – advanced tool for automatically finding
  Secretary Nicholson segments from a diarized JSON file.
- `annotate_segments.py` – annotate `markup_guide.txt` with START/END lines
  using `segments_to_keep.json`.
- `process_video_working.py` – older version of the pipeline kept for
  reference; generally not used.
- `clip_transcripts.py` – produces a `clip_transcripts.txt` summary of
  transcript lines for each clip.

## Scripts folder pipeline

The `scripts/` directory contains one file per pipeline stage. Each script
provides a minimal CLI and can be run independently. `run_pipeline.py`
combines them in order.

### Steps

1. **Transcription** – `scripts/transcribe_step.py`

   ```bash
   python3 scripts/transcribe_step.py --input input.mp4 [--hf_token TOKEN] [--diarize]
   ```
   Creates `markup_guide.txt` and `<input>.json`.

2. **Prepare for editing** – `scripts/json_to_editable_step.py`

   ```bash
   python3 scripts/json_to_editable_step.py <input.json>
   ```
   Produces `segments_edit.json` with `keep` flags and context fields.

3. **Mark clips**

   - Set `keep` flags in `segments_edit.json` and run
     `scripts/identify_clips_json_step.py`.
   - Alternatively, mark ranges directly in `markup_guide.txt` and run
     `scripts/extract_marked_step.py`.
   - `scripts/auto_mark_nicholson_step.py` automatically marks Secretary
     Nicholson segments from a diarized JSON file.
   - `scripts/auto_segment_nicholson_step.py` applies advanced heuristics to
     group Nicholson's comments with surrounding context.
   - `scripts/annotate_segments_step.py` inserts `{START}`/`{END}` markers into
     `markup_guide.txt` based on the chosen segments.

4. **Generate clips** – `scripts/generate_clips_step.py`

   ```bash
   python3 scripts/generate_clips_step.py --input input.mp4 --json segments_to_keep.json
   ```
   Produces numbered clips in the `clips/` directory.

5. **Concatenate** – `scripts/concatenate_clips_step.py`

   ```bash
   python3 scripts/concatenate_clips_step.py --clips_dir clips --out final_video.mp4
   ```
   Joins the clips with white flashes.

6. **Clip transcripts** – `scripts/clip_transcripts_step.py`

   ```bash
   python3 scripts/clip_transcripts_step.py --segments segments_to_keep.json \
       --markup markup_guide.txt --out clip_transcripts.txt
   ```

   Produces a text summary of transcript lines for each retained clip.

7. **Orchestrate everything** – `scripts/run_pipeline.py`

   Pass `--all` to run the entire sequence or combine individual flags.

   ```bash
   python3 scripts/run_pipeline.py --input input.mp4 --all
   ```

## Examples

The `videos/example/` folder shows example outputs generated by these tools
(except for the video files themselves).


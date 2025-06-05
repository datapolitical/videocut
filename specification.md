# VideoCut Specification

This document describes the functional behavior of the VideoCut project and
serves as a reference for re‑implementing the same logic in another language or
refactoring it in Python. The goal is to provide a clear outline for an LLM or
developer to reproduce the existing features.

---

## 1. Overview

VideoCut implements a small video‑editing pipeline driven by
[WhisperX](https://github.com/m-bain/whisperX) transcripts. The workflow
transcribes an input video, allows manual or automatic selection of segments to
keep, generates polished clip files with fade effects, and concatenates the clips
into a final video. Individual steps are exposed via CLI scripts under
`videocut/cli/steps` and can be orchestrated with `run_pipeline.py` or the
monolithic `process_video.py` / `lightweight_process.py` wrappers.

High‑level workflow:

1. **Transcribe** – run WhisperX to produce a JSON transcript and
   `markup_guide.txt`.
2. **Prepare** – convert the JSON to an editable format (TSV or JSON).
3. **Mark clips** – mark segments to keep either manually or using Nicholson
   auto‑detection.
4. **Generate clips** – cut clips with fade‑in/out.
5. **Concatenate** – join clips together with white flashes in between.
6. **Optional utilities** – annotate markup with `{START}`/`{END}` markers and
   generate a transcript summary of long clips.

---

## 2. Requirements

- Python 3.11+
- `ffmpeg` and `ffprobe` available on the system `PATH`
- WhisperX installed along with its dependencies (`requirements.txt`)
- Optional: Hugging Face access token (`HF_TOKEN`) for diarization

---

## 3. Core Modules

### `videocut/core/transcribe.py`

- `is_apple_silicon()` – returns `True` on ARM‑based macOS.
- `transcribe(input_video, hf_token=None, diarize=False)` – runs WhisperX on the
  given video. Sets `compute_type` to `float32` on Apple silicon, otherwise
  `float16`. Produces `<input>.json` and writes `markup_guide.txt` with lines in
  the form `[start-end] SPEAKER: text`.
  - When `diarize=True`, requires a Hugging Face token and passes
    `--diarize --hf_token` to WhisperX.
  - Exits if the JSON file is not produced.

### `videocut/core/clip_utils.py`

Utilities for converting transcripts, identifying clips, generating clips, and
concatenating them.

- **JSON → TSV** – `json_to_tsv(json_path, out_tsv="input.tsv")`
  - Writes a tab‑separated file with `start`, `end`, `speaker`, `text`, and an
    empty `keep` column.
- **JSON → editable JSON** – `json_to_editable(json_path, out_json)`
  - Produces a list of segment objects with `id`, `start`, `end`, `Timestamp`,
    `content`, `speaker`, `pre`, `post`, and `keep` fields.
- **TSV → JSON** – `identify_clips(tsv, out_json)`
  - Reads rows where the `keep` column is truthy and writes a simple JSON list of
    `{start, end}` objects.
- **editable JSON → JSON** – `identify_clips_json(edit_json, out_json)`
  - Saves segments whose `keep` flag is truthy into the same `{start, end}`
    structure.
- **markup guide → JSON** – `extract_marked(markup, out_json)`
  - Parses `markup_guide.txt` looking for `{START}` and `{END}` markers and dumps
    the corresponding segments.
- **Nicholson helpers**:
  - `map_nicholson_speaker(diarized_json)` – heuristically find the speaker label
    for Secretary Nicholson based on key phrases.
  - `auto_segments_for_speaker(diarized_json, speaker_id, out_json)` – dump all
    segments spoken by the given speaker to JSON.
  - `auto_mark_nicholson(diarized_json, out_json)` – convenience wrapper that
    finds Nicholson and writes the segments file.
- **Clip generation** – `generate_clips(input_video, seg_json, out_dir="clips")`
  - For each segment in the JSON file, extracts the portion using `ffmpeg`,
    re‑encodes with fade‑in/out and pads to 1280×720 at 30fps.
- **Concatenation** – `concatenate_clips(clips_dir="clips", out_file)`
  - Concatenates `clip_*.mp4` files, inserting a white flash (`0.5` seconds)
    between them. Uses `ffprobe` to detect resolution and joins audio/video
    streams with the `concat` filter.

### `auto_segment_nicholson.py`

Standalone script and importable functions for automatically determining which
segments belong to Secretary Nicholson when diarization is available.
Heuristics group nearby segments, trim unrelated roll‑call portions, and attach
context lines before and after each segment. Results are saved as a list of
objects with `start`, `end`, `text`, `pre`, and `post` keys.

### Additional Utilities

- `annotate_segments.py` – inserts `{START}`/`{END}` markers into
  `markup_with_markers.txt` for the segments in `segments_to_keep.json`.
- `clip_transcripts.py` – writes `clip_transcripts.txt` summarizing the transcript
  lines for each kept segment (skipping clips with fewer than eight words).

---

## 4. CLI Step Scripts (`videocut/cli/steps`)

Each script wraps a single function from the core modules, exposing one
command‑line step:

1. `transcribe_step.py` – run WhisperX transcription.
2. `json_to_editable_step.py` – convert WhisperX JSON to `segments_edit.json`.
3. `identify_clips_json_step.py` – parse the editable JSON and produce
   `segments_to_keep.json`.
4. `extract_marked_step.py` – parse `{START}`/`{END}` markers from
   `markup_guide.txt`.
5. `auto_mark_nicholson_step.py` – auto‑mark Nicholson segments from a diarized
   JSON file.
6. `generate_clips_step.py` – cut clips to a directory using the JSON segments.
7. `concatenate_clips_step.py` – assemble the clips into the final video.
8. `clip_transcripts_step.py` – generate transcript summaries for each clip.
9. `annotate_segments_step.py` – produce `markup_with_markers.txt` showing the
   segments in context.
10. `run_pipeline.py` – orchestrate all steps with `--all` or individual flags.

---

## 5. Monolithic Wrappers

- `process_video.py` – one CLI with flags to enable or disable each step.
- `lightweight_process.py` – similar to `process_video.py` but optionally invokes
  `auto_mark_nicholson` when requested.

---

## 6. Example Data

`videos/` contains example transcript and JSON outputs used for testing. No
video files are included.

---

## 7. Tests

`tests/` provide minimal coverage:

- `test_core.py` verifies that `transcribe()` runs WhisperX with the correct
  compute type and that `generate_clips()` invokes `ffmpeg` and the fade helper.
- `test_auto_segment_nicholson.py` ensures `find_nicholson_speaker()` returns
  `None` when no cues exist.

Running `pytest` should result in all tests passing.

---

## 8. Re‑implementation Notes

To duplicate or refactor this project in another language (or a cleaner Python
rewrite), follow these guidelines:

1. **Command‑line interface** – maintain the same step names and argument
   structure so the pipeline can be scripted in the same manner.
2. **WhisperX invocation** – replicate the call with appropriate options
   (`--compute_type`, `--output_dir`, optional `--diarize` and `--hf_token`).
   Ensure the generated JSON is parsed identically.
3. **Segment representation** – the core utilities operate on a simple JSON list
   of `{start, end}` floats. Keep this structure for interoperability.
4. **Clip generation** – use `ffmpeg` to extract each segment, then re‑encode with
   fade‑in/out effects and padding to `1280x720` at `30fps`. Insert white flashes
   between clips when concatenating.
5. **Nicholson heuristics** – if replicating `auto_segment_nicholson.py`, match
   the text‑based heuristics for grouping segments and trimming based on end
   phrases ("thank you", "next item", etc.).
6. **Outputs** – the process produces:
   - `<input>.json` and `markup_guide.txt` from transcription
   - `segments_edit.json` or `input.tsv` for manual editing
   - `segments_to_keep.json` listing the final clip boundaries
   - `clips/clip_XXX.mp4` files
   - `final_video.mp4`
   - Optional: `markup_with_markers.txt` and `clip_transcripts.txt`
7. **Environment** – ensure `FFmpeg` and `ffprobe` binaries are accessible.
   Speaker diarization requires a Hugging Face token via `--hf_token` or the
   `HF_TOKEN` environment variable.

Adhering to these behaviors will yield a compatible replacement for the current
VideoCut implementation.


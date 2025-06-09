# VideoCut Specification

This document describes the functional behavior of the VideoCut project. It provides a reference for recreating the same features in any environment.

---

## 1. Overview

VideoCut implements a video-editing pipeline driven by transcript data. The workflow transcribes an input video, allows manual or automatic selection of segments to keep, generates polished clip files with fade effects, and concatenates the clips into a final video. Individual steps are available as command-line scripts and can be orchestrated by a pipeline runner.

High-level workflow:

1. **Transcribe with diarization** – produce a speaker-labeled JSON transcript and `markup_guide.txt`.
2. **Identify segments** – create `segments_to_keep.json` selecting Secretary Nicholson's speech. The script cross-checks heuristics against recognized speakers and warns if they disagree. The JSON can be manually edited or converted to an editable format after this step.
3. **Generate clips** – cut clips with fade-in/out.
4. **Concatenate** – join clips together with white flashes in between.
5. **Annotate markup** – create `markup_with_markers.txt` for the kept segments.
6. **Clip transcripts** – summarize transcript lines for each long clip.

---

## 2. Requirements

- A transcription engine capable of producing JSON output
- Command-line video processing tools for clipping and concatenation
- Access token for speaker diarization

---

## 3. Core Functionality

### Transcription

- Automatically selects an appropriate compute mode based on the hardware architecture.
- Transcribes the input video to produce `<input>.json` and `markup_guide.txt` with lines in the form `[start-end] SPEAKER: text`.
- Always performs diarization using the provided access token.
- Exits if the expected JSON file is not produced.

### Clip utilities

These utilities convert transcripts, identify clips, generate clips, and concatenate them.

- **JSON → TSV** – convert a transcript to a tab-separated file with `start`, `end`, `speaker`, `text`, and an empty `keep` column.
- **JSON → editable JSON** – produce a list of segment objects containing timing, text, and metadata for manual editing.
- **TSV → JSON** – read rows where the `keep` column is truthy and output a list of `{start, end}` objects.
- **editable JSON → JSON** – save segments whose `keep` flag is truthy into the same `{start, end}` structure.
- **markup guide → JSON** – parse `markup_guide.txt` looking for `{START}` and `{END}` markers and dump the corresponding segments.
- **Nicholson helpers** – map the speaker label for Secretary Nicholson, dump all of that speaker's segments, and provide a convenience function to identify Nicholson segments automatically.
- **Clip generation** – for each segment in the JSON file, extract the portion, re-encode it with fade-in/out, and pad to 1280×720 at 30fps.
- **Concatenation** – concatenate the clip files, inserting a white flash (`0.5` seconds) between them and joining audio/video streams.

### Automatic Nicholson segmentation

Functions for automatically determining which segments belong to Secretary Nicholson when diarization data is available. Heuristics group nearby segments, trim unrelated portions, and attach context lines before and after each segment. Results are saved as a list of objects with `start`, `end`, `text`, `pre`, and `post` keys.

### Chair detection and roll call mapping

The roll call portion of a meeting identifies the chair and validates speaker
labels. When the transcript contains a phrase like "call the roll," the speaker
issuing that line is considered the chair. Each name read during the roll call
is paired with the responding speaker who says "present" or "here." This mapping
is returned for downstream validation.

### Additional utilities

- Insert `{START}`/`{END}` markers into `markup_with_markers.txt` for the segments in `segments_to_keep.json`.
- Write `clip_transcripts.txt` summarizing the transcript lines for each kept segment, skipping clips with fewer than eight words.

---

## 4. CLI Step Scripts

Each script wraps one of the core functions, exposing a single command-line step:

1. Transcribe a video.
2. Convert the JSON transcript to `segments_edit.json`.
3. Parse the editable JSON and produce `segments_to_keep.json`.
4. Extract `{START}`/`{END}` markers from `markup_guide.txt`.
5. Identify Nicholson segments from a diarized JSON file.
6. Cut clips to a directory using the JSON segments.
7. Assemble the clips into the final video.
8. Generate transcript summaries for each clip.
9. Produce `markup_with_markers.txt` showing the segments in context.
10. Orchestrate all steps with a pipeline command.

---

## 5. Monolithic Wrappers

A single command-line interface can run the entire pipeline with flags to enable or disable each step. The default behavior is to identify Nicholson segments immediately after transcription, producing `segments_to_keep.json`. Manual editing of this file can be done before generating clips, and the segment identification step can be skipped via a flag.

---

## 6. Example Data

`videos/` contains example transcript and JSON outputs used for testing. No video files are included.

---

## 7. Tests

The test suite verifies that transcription selects the correct compute type, that clip generation invokes the video-processing tool and the fade helper, and that Nicholson detection returns `None` when no cues exist. Running the tests should result in all checks passing.

---

## 8. Re-implementation Notes

To recreate this project in another environment, follow these guidelines:

1. **Command-line interface** – maintain the same step names and argument structure so the pipeline can be scripted in the same manner.
2. **Transcription invocation** – replicate the call with the appropriate options and ensure the generated JSON is parsed identically.
3. **Segment representation** – the utilities operate on a simple JSON list of `{start, end}` floats. Keep this structure for interoperability.
4. **Clip generation** – extract each segment using a video-processing tool, then re-encode with fade-in/out effects and padding to `1280x720` at `30fps`. Insert white flashes between clips when concatenating.
5. **Nicholson heuristics** – match the text-based heuristics for grouping segments and trimming based on end phrases ("thank you", "next item", etc.).
6. **Outputs** – the process produces:
   - `<input>.json` and `markup_guide.txt` from transcription
   - `segments_edit.json` or `input.tsv` for manual editing
   - `segments_to_keep.json` listing the final clip boundaries
   - `clips/clip_XXX.mp4` files
   - `final_video.mp4`
   - `markup_with_markers.txt`
   - `clip_transcripts.txt`
7. **Environment** – ensure the video-processing binaries are accessible. Speaker diarization requires an authentication token when used.

Adhering to these behaviors will yield a compatible replacement for the current VideoCut implementation.


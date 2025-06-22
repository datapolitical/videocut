# VideoCut

VideoCut turns a recorded board meeting into a polished highlight reel. The tools align a written transcript with the video, detect remarks from Secretary Nicholson and cut the results into shareable clips.

## Requirements
- Python 3.11+
- [FFmpeg](https://ffmpeg.org/) available on your `PATH`
- [WhisperX](https://github.com/m-bain/whisperX) and its Python dependencies
- `HF_TOKEN` environment variable when using the diarization features

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
make install
pytest
```
For a lightweight install without transcription dependencies:

```bash
pip install -e .[light]
```

## Workflow
0. **Download Meeting Transcript & Video from Youtube & trim**
   - Download the meeting transcript from RTD.
   - Run:
      - `chmod +x download-meeting.sh`
      - `./download-meeting.sh "MEETING_YOUTUBE_VIDEO_URL"` (meeting URL in quotes)
   - This script downloads the meeting video. Move the video and transcript into a folder.
   - After downloading, if the meeting was delayed, trim the video to start at the beginning of the meeting so it aligns with the printed transcript.
1. **Transcribe & align** – `videocut transcribe May_Board_Meeting.mp4 --pdf transcript.pdf`
   - Extracts dialogue from the PDF, aligns it to the video and writes
     `transcript.txt` with lines in the form
     `[start‑end] NAME: text`.
   - WhisperX generates `May_Board_Meeting.json`, `May_Board_Meeting.tsv`,
     `May_Board_Meeting.srt`, `May_Board_Meeting.vtt` and `May_Board_Meeting.txt`.

### Transcription Backends

VideoCut supports multiple local transcription backends:

- `whisperx` (default): Uses WhisperX via CLI subprocess.
- `mlx`: Uses Apple's MLX-Whisper for fast on-device transcription (Apple Silicon only).
- `whispercpp`: Runs the bundled static `whisper` binary.

Example usage:

```bash
videocut transcribe myvideo.mp4 --backend mlx
# or use whisper.cpp
videocut transcribe myvideo.mp4 --backend whispercpp
```

Requirements:

* macOS with Apple Silicon (M1/M2/M3)
* `mlx` and `mlx-whisper` Python packages
* `ffmpeg` must be installed and in your system path
* for `whispercpp` download `ggml-small.en-q8.bin` into `tools/models`

2. **Identify segments** – `videocut identify-segments May_Board_Meeting.json`
   - Creates a tab‑indented `segments.txt` containing `=START=` and `=END=`
     markers for each Nicholson segment.
2a. *(optional)* Edit `segments.txt` to trim or reorder the segments.
2b. You can also run `videocut segment transcript.txt` on a raw, flush‑left
    transcript. The CLI will print "Using new segmenter 2.0 code" when this
    code path is triggered.
3. **Generate clips** – `videocut generate-and-align May_Board_Meeting.mp4 segments.txt`
   - Buffers and re‑aligns each segment, trims to word boundaries and saves the
     final clips to `clips/`. Alignment data for each clip is written as
     `clip_###_aligned.json` with a summary in `timestamps.json`.
   - `generate-and-align` also accepts a JSON segments file for simpler workflows.
   - Use `videocut clip` to cut clips exactly as specified in `segments.txt` without alignment.
4. **Concatenate** – `videocut concatenate`
   - Joins clips with a dip-to-white transition by default, creating
     `final_video.mp4`. Use `--dip` to customize the color and timing or
     `--dip-news` for a preset news-style flash.
5. **Preview fades** – `videocut preview-fades`
   - Generates 20 sample crossfades between `clip_000.mp4` and `clip_001.mp4`
     in the `fade_previews/` directory.

## Package layout
- `videocut/cli.py` – command line interface implemented with Typer
- `videocut/core/` – reusable helpers
- `videos/` – example data used by the tests

### PDF transcript cleanup
If a diarized JSON transcript already exists you can replace its text using an
official PDF with:
```bash
videocut pdf-transcript existing.json transcript.pdf
```

To regenerate `transcript.txt` from a diarized JSON and an official PDF:
```bash
videocut json-to-transcript May_Board_Meeting.json transcript.pdf
```

### Additional transcript utilities
Use `pdf-extract` to create both a text and JSON version of a PDF transcript:
```bash
videocut pdf-extract transcript.pdf
```

You can align those PDF lines to a diarized JSON with `pdf-match`:
```bash
videocut pdf-match transcript.pdf May_Board_Meeting.json
```
This writes `matched.json` where each line's words are paired with their
closest timestamped match from the JSON.

For raw SRT captions you can perform a band-limited DTW alignment with:
```bash
videocut dtw-align pdf_transcript.txt May_Board_Meeting.srt
```
This generates `matched_dtw.json`. Token timestamps are evenly spread across each
caption's duration for better alignment accuracy. Use ``make-labeled`` to create
a speaker-tagged transcript:
```bash
videocut make-labeled matched_dtw.json -o dtw_transcript_labeled.txt
```
The resulting ``dtw_transcript_labeled.txt`` is ready for ``videocut segment``.

### 3 · Match (NEW)

```bash
videocut match pdf_transcript.json May_Board_Meeting.json
```

Produces `matched.json` where every PDF line now carries precise start/end
timestamps taken from the ASR word stream. Down-stream commands
(`identify-segments`, `generate-and-align`, `concatenate`) consume `matched.json`
in place of `pdf_transcript.json`.

Run `check-transcript` to flag segments with unusual timing:
```bash
videocut check-transcript May_Board_Meeting.json
```
This reports any segments whose words per second fall outside the normal range.

### 4 · Convert to TXT (NEW)

```bash
videocut to-txt matched.json       # ⇒ transcript.txt
```

`transcript.txt` is the input expected by **`videocut segment`**.

### 5 · Make Labeled Transcript (NEW)

```bash
videocut make-labeled matched.json -o labeled_transcript.txt
```

Use this when a matched JSON is missing speaker tags. The output can be fed
directly to ``videocut segment``.

The full pipeline is now:

```
transcribe  →  match/dtw-align  →  segment  →  generate-and-align  →  concatenate

### 6 · Install / Run Cheat-sheet

```bash
Step #1
(Step one should take an mp4 file and a matching pdf transcript)
videocut transcribe May_Board_Meeting.mp4
videocut pdf-extract transcript.pdf
videocut dtw-align pdf_transcript.txt May_Board_Meeting.srt
videocut segment transcript.txt
(Step 2 should take the same mp4 file and a segmented transcript, and accept the flags for concatenate)
Step #2
videocut clip videocut clip May_Board_Meeting.mp4 segments.txt
videocut concatenate --dip-news
```

## 📤 Uploading to YouTube

### Step 1: Authorize access (first time only)

```bash
videocut authorize --client-secret client_secret.json --output credentials.json
```

- Get `client_secret.json` from your Google Cloud Console (OAuth credentials).
- This saves a `credentials.json` file used for uploads.

### Step 2: Upload video with chapters

```bash
videocut upload final.mp4 --creds credentials.json
```

By default, this reads `segments.txt` and generates a YouTube description with clickable chapters.

| Flag | Description |
|------|-------------|
| `--title` | Title for the uploaded video |
| `--tags` | Tags to associate with the video |
| `--privacy` | `public`, `unlisted` (default), `private` |
| `--segments` | Path to `segments.txt` |
| `--fade` | Transition length in seconds (default 0.5) |


Download the Whisper.cpp model once:
```bash
wget -O tools/models/ggml-small.en-q8.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en-q8_0.bin
```

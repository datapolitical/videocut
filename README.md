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
1. **Transcribe & align** – `videocut transcribe May_Board_Meeting.mp4 --pdf transcript.pdf`
   - Extracts dialogue from the PDF, aligns it to the video and writes
     `transcript.txt` with lines in the form
     `[start‑end] NAME: text`.
   - WhisperX generates `May_Board_Meeting.json`, `May_Board_Meeting.tsv`,
     `May_Board_Meeting.srt`, `May_Board_Meeting.vtt` and `May_Board_Meeting.txt`.
2. **Identify segments** – `videocut identify-segments May_Board_Meeting.json`
   - Creates a tab‑indented `segments.txt` containing `=START=` and `=END=`
     markers for each Nicholson segment.
2a. *(optional)* Edit `segments.txt` to trim or reorder the segments.
2b. You can also run `videocut segment transcript.txt` on a raw, flush‑left
    transcript. The CLI will print "Using new segmenter 2.0 code" when this
    code path is triggered.
3. **Generate clips** – `videocut generate-clips May_Board_Meeting.mp4 segments.txt`
   - Buffers and re‑aligns each segment, trims to word boundaries and saves the
     final clips to `clips/`. Alignment data for each clip is written as
     `clip_###_aligned.json` with a summary in `timestamps.json`.
   - `generate-clips` also accepts a JSON segments file for simpler workflows.
4. **Concatenate** – `videocut concatenate`
   - Joins all clips with a fade to white between each one, creating
     `final_video.mp4`.

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
videocut json-to-transcript May_Board_Meeting.json videos/May_Board_Meeting/transcript.pdf
```

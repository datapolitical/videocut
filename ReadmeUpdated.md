# VideoCut Command Guide

This short guide explains how to run the most common VideoCut commands.
The examples use the provided `May_Board_Meeting.mp4` sample video and an
optional transcript `transcript.pdf`.

## 1. Transcription

### `videocut transcribe May_Board_Meeting.mp4`
Run WhisperX on the video and create the baseline transcript files.  Outputs
include:

- `May_Board_Meeting.json` – word‑level JSON transcript
- `May_Board_Meeting.tsv` – tab separated words
- `May_Board_Meeting.srt` / `.vtt` – caption formats
- `May_Board_Meeting.txt` – plain text transcript

### `videocut transcribe May_Board_Meeting.mp4 --pdf transcript.pdf`
If you supply an official PDF transcript the command extracts the dialogue from
that PDF, aligns it to the ASR output and produces `transcript.txt`.  The result
is a tab‑indented file with lines formatted as:

```
[start - end] NAME: text
```

`transcript.txt` becomes the input for later segmentation steps.

## 2. Extract text from a PDF

### `videocut pdf-extract transcript.pdf`
Creates two files next to the PDF:

- `pdf_transcript.txt` – one line per utterance
- `pdf_transcript.json` – JSON list of those lines and tokenized words

These files can be fed to `match`, `pdf-match` or `dtw-align` for alignment.

## 3. Align PDF text to SRT captions

### `videocut dtw-align pdf_transcript.txt May_Board_Meeting.srt`
Performs a band‑limited Dynamic Time Warping alignment between a plain text
transcript (`pdf_transcript.txt`) and existing SRT captions.  The command
writes two outputs:

- `matched_dtw.json` – PDF lines with estimated timestamps
- `dtw-transcript.txt` – speaker‑labeled transcript ready for segmentation

## 4. Segment the transcript

### `videocut segment transcript.txt`
Parses a raw or labeled `transcript.txt` and generates `segments.txt` containing
`=START=` and `=END=` markers around each Secretary Nicholson segment.  When a
plain text file is provided, the CLI prints "Using new segmenter 2.0 code" to
indicate the modern path is used.

## 5. Concatenate clips

### `videocut concatenate`
Looks inside the `clips/` directory and joins all `clip_###.mp4` files into a
single `final_video.mp4`.  A dip‑to‑white flash is inserted between clips.  Use
`--dip-fast` for a quicker transition.


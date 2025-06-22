# VideoCut Quickstart

This short guide walks through a typical workflow using the `videocut` command line interface. Each step can be run individually or you can use the simplified `prep` and `build` commands to automate the process.

## Basic Pipeline

```bash
videocut transcribe video.mp4
videocut pdf-extract transcript.pdf
videocut align pdf_transcript.txt video.srt
videocut segment transcript.txt
videocut clip video.mp4 segments.txt
videocut concatenate --dip-news
```

### transcribe
Run WhisperX (or another backend like whispercpp or MLX) on `video.mp4` and create transcription files.

```
videocut transcribe VIDEO [--diarize] [--hf-token TOKEN] [--speaker-db FILE]
                    [--progress / --no-progress] [--pdf PATH]
                    [--backend whisperx|whispercpp|mlx]
```
Flags:
- `--diarize` – perform speaker diarization.
- `--hf-token TOKEN` – Hugging Face token required for diarization. The CLI also reads `HF_TOKEN` from the environment, including variables in a `.env` file.
- `--speaker-db FILE` – speaker embedding database JSON.
- `--progress / --no-progress` – show or hide progress output.
- `--pdf PATH` – align an official PDF transcript.
- `--backend whisperx|whispercpp|mlx` – choose transcription backend.
For `whispercpp` place `ggml-small.en-q8.bin` in `tools/models/`.

### pdf-extract
Extract the meeting transcript from a PDF.

```
videocut pdf-extract FILE [--txt-out TXT] [--json-out JSON]
```
Flags:
- `--txt-out TXT` – extracted text output path (default `pdf_transcript.txt`).
- `--json-out JSON` – JSON output path (default `pdf_transcript.json`).

### align
Align the PDF transcript to an existing SRT caption file.

```
videocut align PDF_TXT VIDEO_SRT [--json-out JSON] [--txt-out TXT]
                                     [--band N]
```
Flags:
- `--json-out JSON` – write aligned data to this file (default `matched_dtw.json`).
- `--txt-out TXT` – labeled transcript output path (default `dtw-transcript.txt`).
- `--band N` – DTW radius for alignment.

### segment
Detect remarks from Director Nicholson in a transcript.

```
videocut segment FILE [--speaker NAME] [--out PATH] [--debug]
```
Flags:
- `--speaker NAME` – name of the speaker to extract (default `Chris Nicholson`).
- `--out PATH` – output segments file path (default `segments.txt`).
- `--debug` – show debug information during segmentation.

### clip
Cut clips according to `segments.txt`.

```
videocut clip VIDEO SEGMENTS [--out-dir DIR] [--srt-file FILE]
```
Flags:
- `--out-dir DIR` – directory for generated clips (default `clips`).
- `--srt-file FILE` – optional SRT captions to cut with the clips.

### concatenate
Join the clips with dip‑to‑white transitions (use `--dip-news` for preset timing).

```
videocut concatenate [--clips-dir DIR] [--output FILE] [--dip] [--dip-news]
                     [--dip-color HEX] [--fade-duration SEC]
                     [--hold-duration SEC]
```
Flags:
- `--clips-dir DIR` – directory containing clip files (default `clips`).
- `--output FILE` – path to the concatenated video (default `final_video.mp4`).
- `--dip` – add dip‑to‑white transitions between clips.
- `--dip-news` – use preset news‑style dip timing.
- `--dip-color HEX` – color of the dip flash.
- `--fade-duration SEC` – fade time in seconds.
- `--hold-duration SEC` – hold time for the white frame.

## Streamlined Commands

Two helper commands automate the above steps:

### prep
Transcribe a video, extract and align the PDF transcript, and produce `segments.txt`.

```
videocut prep [VIDEO] [PDF] [--band N]
```
Flags:
- `--band N` – DTW radius used when aligning the PDF transcript.

### build
Cut clips from a video using `segments.txt` and concatenate them.

```
videocut build [VIDEO] [SEGMENTS] [--out-dir DIR] [--output FILE]
               [--dip] [--dip-news] [--dip-color HEX]
               [--fade-duration SEC] [--hold-duration SEC]
               [--srt-file FILE]
```
Flags:
- `--out-dir DIR` – directory containing clips (default `clips`).
- `--output FILE` – final video output path (default `final_video.mp4`).
- `--dip` – add dip‑to‑white transitions.
- `--dip-news` – use preset news‑style timing.
- `--dip-color HEX` – color used for the dip flash.
- `--fade-duration SEC` – fade time in seconds.
- `--hold-duration SEC` – hold time for the white frame.
- `--srt-file FILE` – optional SRT to annotate clips.

With these two commands you can run the full workflow as:

```bash
videocut prep video.mp4 transcript.pdf
videocut build video.mp4 segments.txt
```

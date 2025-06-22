# VideoCut Quickstart

This short guide walks through a typical workflow using the `videocut` command line interface. Each step can be run individually or you can use the simplified `prep` and `build` commands to automate the process.

## Basic Pipeline

```bash
videocut transcribe video.mp4
videocut pdf-extract transcript.pdf
videocut dtw-align pdf_transcript.txt video.srt
videocut segment transcript.txt
videocut clip video.mp4 segments.txt
videocut concatenate --dip-news
```

### transcribe
Run WhisperX (or another backend) on `video.mp4` and create transcription files.

```
videocut transcribe VIDEO [--diarize] [--hf-token TOKEN] [--speaker-db FILE]
                    [--progress / --no-progress] [--pdf PATH]
                    [--backend whisperx|mlx]
```

### pdf-extract
Extract the meeting transcript from a PDF.

```
videocut pdf-extract FILE [--txt-out TXT] [--json-out JSON]
```

### dtw-align
Align the PDF transcript to an existing SRT caption file.

```
videocut dtw-align PDF_TXT VIDEO_SRT [--json-out JSON] [--txt-out TXT]
                                     [--band N]
```

### segment
Detect remarks from Director Nicholson in a transcript.

```
videocut segment FILE [--speaker NAME] [--out PATH] [--debug]
```

### clip
Cut clips according to `segments.txt`.

```
videocut clip VIDEO SEGMENTS [--out-dir DIR] [--srt-file FILE]
```

### concatenate
Join the clips with dip‑to‑white transitions (use `--dip-news` for preset timing).

```
videocut concatenate [--clips-dir DIR] [--output FILE] [--dip] [--dip-news]
                     [--dip-color HEX] [--fade-duration SEC]
                     [--hold-duration SEC]
```

## Streamlined Commands

Two helper commands automate the above steps:

### prep
Transcribe a video, extract and align the PDF transcript, and produce `segments.txt`.

```
videocut prep [VIDEO] [PDF] [--band N]
```

### build
Cut clips from a video using `segments.txt` and concatenate them.

```
videocut build [VIDEO] [SEGMENTS] [--out-dir DIR] [--output FILE]
               [--dip] [--dip-news] [--dip-color HEX]
               [--fade-duration SEC] [--hold-duration SEC]
               [--srt-file FILE]
```

With these two commands you can run the full workflow as:

```bash
videocut prep video.mp4 transcript.pdf
videocut build video.mp4 segments.txt
```

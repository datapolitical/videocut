# VideoCut

VideoCut turns recorded board meetings into polished clips with minimal effort. Provide a video file and its transcript and the `videocut` command aligns each word, detects Secretary Nicholson's remarks, and cuts shareable clips.

## Requirements
- Python 3.11+
- [FFmpeg](https://ffmpeg.org/) on your `PATH`
- [WhisperX](https://github.com/m-bain/whisperX) and its dependencies
- `HF_TOKEN` environment variable for speaker diarization

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Workflow
1. **Align transcript** –
   `videocut align input.mp4 transcript.txt` extracts the audio and aligns the
   text, producing `aligned.json`.
2. *(Optional)* **Apply PDF transcript** – `videocut pdf-transcript aligned.json transcript.pdf`
   matches the JSON with an official PDF when available; see the cleanup section below.
3. **Identify segments** – `videocut identify-segments aligned.json` writes a
   tab‑indented `segments.txt` grouping Secretary Nicholson's remarks.
4. *(Optional)* **Edit `segments.txt`** – trim or rearrange lines before generating clips.
5. **Generate clips** –
   `videocut generate-clips input.mp4` reads `segments.txt` (and matching SRT captions) and cuts clips to `clips/`.
6. **Concatenate** – `videocut concatenate` joins clips into `final_video.mp4`.


## Package layout
- `videocut/cli.py` – Typer command line interface
- `videocut/core/` – modular helpers
- `videos/` – example data used for testing

### PDF transcript cleanup

If an official `transcript.pdf` is available you can apply it to a diarized
`input.json` using the new command:

```bash
videocut pdf-transcript \
    videos/May_Board_Meeting/May_Board_Meeting.json \
    videos/May_Board_Meeting/transcript.pdf
```

If you are running the ASR workflow, you can pass `--pdf transcript.pdf` to
`videocut transcribe` or `videocut pipeline` to fold this step into the process.
The parsed text replaces the diarized transcript and improves subsequent
segmentation with `identify-segments`.



from __future__ import annotations
import json
import os
import subprocess
import tempfile
from pathlib import Path
import wave
import contextlib
import shutil

from .. import parse_pdf_text

import torch
import whisperx


_DEFAULT_OUT = "aligned.json"


def align_with_transcript(video: str, transcript: str, out_json: str = _DEFAULT_OUT) -> None:
    """Align *transcript* with *video* audio and write ``out_json``.

    If ``transcript`` is a PDF file it is first converted to plain text which is
    saved alongside the PDF with a ``.txt`` extension.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"

    if shutil.which("ffmpeg") is None and not os.environ.get("VIDEOCUT_SKIP_FFMPEG_CHECK"):
        raise RuntimeError("ffmpeg not found on PATH. Please install FFmpeg and try again.")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        audio_path = tmp.name
    print(f"🎞️  extracting audio to {audio_path}")

    try:
        subprocess.run([
            "ffmpeg",
            "-v",
            "error",
        "-y",
        "-i",
        video,
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        "-f",
        "wav",
        audio_path,
        ], check=True)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg executable not found")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg failed with exit code {e.returncode}")

    with contextlib.closing(wave.open(audio_path, "rb")) as wf:
        audio_duration = wf.getnframes() / float(wf.getframerate())

    align_model, meta = whisperx.load_align_model("en", device)

    txt_path: Path | None = None
    if transcript.lower().endswith(".pdf"):
        lines = parse_pdf_text.parse_pdf(transcript)
        text = "\n".join(lines)
        txt_path = Path(transcript).with_suffix(".txt")
        txt_path.write_text(text + "\n")
    else:
        text = Path(transcript).read_text().strip()

    segments = [{"text": text, "start": 0.0, "end": audio_duration}]
    print("🧭  aligning transcript …")
    aligned = whisperx.align(segments, align_model, meta, audio_path, device)

    Path(out_json).write_text(json.dumps(aligned["word_segments"], indent=2))
    os.remove(audio_path)
    print(f"🗑️  temporary audio removed")
    if txt_path is not None:
        print(f"\N{CHECK MARK} transcript text → {txt_path}")
    print(f"\N{CHECK MARK} alignment written to {out_json}")


__all__ = ["align_with_transcript"]

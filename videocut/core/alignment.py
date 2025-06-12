from __future__ import annotations
import json
import os
import subprocess
import tempfile
from pathlib import Path

import torch
import whisperx


_DEFAULT_OUT = "aligned.json"


def align_with_transcript(video: str, transcript: str, out_json: str = _DEFAULT_OUT) -> None:
    """Align *transcript* with *video* audio and write ``out_json``."""
    device = "cuda" if torch.cuda.is_available() else "cpu"

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        audio_path = tmp.name

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

    align_model, meta = whisperx.load_align_model("en", device)
    segments = [{"text": Path(transcript).read_text().strip()}]
    aligned = whisperx.align(segments, align_model, meta, audio_path, device)

    Path(out_json).write_text(json.dumps(aligned["word_segments"], indent=2))
    os.remove(audio_path)
    print(f"\N{CHECK MARK} alignment written to {out_json}")


__all__ = ["align_with_transcript"]

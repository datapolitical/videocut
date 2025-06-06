"""Transcription utilities using WhisperX."""
from __future__ import annotations
import json
import platform
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def is_apple_silicon() -> bool:
    """Return True if running on Apple Silicon."""
    return platform.system() == "Darwin" and platform.machine() in {"arm64", "arm"}


def compute_type() -> str:
    """Return compute_type argument for WhisperX based on architecture."""
    return "float32" if is_apple_silicon() else "float16"


def transcribe(video: str, hf_token: str | None = None, diarize: bool = False) -> None:
    """Run WhisperX on *video* and produce markup_guide.txt."""
    out_json = f"{Path(video).stem}.json"
    cmd = ["whisperx", video, "--compute_type", compute_type(), "--output_dir", "."]
    if diarize:
        if not hf_token:
            sys.exit("❌  --diarize requires --hf_token or HF_TOKEN env var")
        cmd += ["--diarize", "--hf_token", hf_token]

    print("🧠  WhisperX …")
    subprocess.run(cmd, check=True)
    if not Path(out_json).exists():
        sys.exit(f"❌  Expected {out_json} not produced")

    segs = json.loads(Path(out_json).read_text())["segments"]
    with open("markup_guide.txt", "w") as g:
        for seg in segs:
            start, end = round(seg["start"], 2), round(seg["end"], 2)
            speaker = seg.get("speaker", "SPEAKER") if diarize else "SPEAKER"
            text = seg["text"].strip().replace("\n", " ")
            g.write(f"[{start}-{end}] {speaker}: {text}\n")
    print("✅  markup_guide.txt ready – edit ranges or use TSV workflow")

__all__ = ["transcribe", "compute_type", "is_apple_silicon"]

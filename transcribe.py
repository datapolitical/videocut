#!/usr/bin/env python3
"""transcribe.py

Literal transcription helper copied verbatim from the last working version.
Contains `is_apple_silicon` and `transcribe()` only.
"""

import json
import platform
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ───────────────────────── Helper ─────────────────────────

def is_apple_silicon() -> bool:
    """Return True if running on Apple‑silicon Mac."""
    return platform.system() == "Darwin" and platform.machine() in {"arm64", "arm"}

# ───────────────────────── Transcribe ────────────────────

def transcribe(input_video: str, hf_token: str | None = None, diarize: bool = False):
    """Run WhisperX on *input_video* and write `markup_guide.txt`.

    This function is copied **verbatim** from the working script so that
    behavior remains identical.
    """
    compute_type = "float32" if is_apple_silicon() else "float16"
    out_json = f"{Path(input_video).stem}.json"

    cmd = [
        "whisperx", input_video,
        "--compute_type", compute_type,
        "--output_dir", ".",
    ]
    if diarize:
        if not hf_token:
            sys.exit("❌  --diarize needs --hf_token or HF_TOKEN env var")
        cmd += ["--diarize", "--hf_token", hf_token]

    print("🧠  WhisperX …")
    subprocess.run(cmd, check=True)
    if not Path(out_json).exists():
        sys.exit(f"❌  Expected {out_json} not produced by WhisperX")

    segs = json.loads(Path(out_json).read_text())["segments"]
    with open("markup_guide.txt", "w") as g:
        for s in segs:
            start, end = round(s["start"], 2), round(s["end"], 2)
            speaker = s.get("speaker", "SPEAKER") if diarize else "SPEAKER"
            text = s["text"].strip().replace("\n", " ")
            g.write(f"[{start}-{end}] {speaker}: {text}\n")
    print("✅  markup_guide.txt ready – edit ranges or use TSV workflow")

__all__ = ["transcribe", "is_apple_silicon"]

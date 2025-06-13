"""Transcription utilities using WhisperX."""
from __future__ import annotations
import json
import platform
import subprocess
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

from . import pdf_utils, segmentation

load_dotenv()


def is_apple_silicon() -> bool:
    """Return True if running on Apple Silicon."""
    return platform.system() == "Darwin" and platform.machine() in {"arm64", "arm"}


def compute_type() -> str:
    """Return compute_type argument for WhisperX based on architecture."""
    return "float32" if is_apple_silicon() else "float16"


def transcribe(
    video: str,
    hf_token: str | None = None,
    diarize: bool = False,
    speaker_db: str | None = None,
    progress: bool = True,
    pdf_path: str | None = None,
) -> None:
    """Run WhisperX on *video* and produce ``markup_guide.txt``.

    If ``speaker_db`` is provided, diarized speaker labels will be mapped to real
    names using embeddings after transcription. Set ``progress`` to ``False`` to
    suppress the WhisperX progress output.
    """
    out_json = f"{Path(video).stem}.json"
    srt_path = Path(video).with_suffix(".srt")
    cmd = ["whisperx", video, "--compute_type", compute_type(), "--output_dir", "."]
    if progress:
        cmd += ["--print_progress", "True"]
    if diarize:
        if not hf_token:
            sys.exit("❌  --diarize requires --hf_token or HF_TOKEN env var")
        cmd += ["--diarize", "--hf_token", hf_token]

    print("🧠  WhisperX …")
    env = os.environ.copy()
    env.setdefault("PYTHONWARNINGS", "ignore")
    subprocess.run(cmd, check=True, env=env)
    if not Path(out_json).exists():
        sys.exit(f"❌  Expected {out_json} not produced")

    if diarize and speaker_db and Path(speaker_db).exists():
        try:
            from .speaker_mapping import apply_speaker_map
            apply_speaker_map(video, out_json, speaker_db, out_json)
        except Exception as exc:
            print(f"⚠️  speaker mapping failed: {exc}")

    if pdf_path:
        try:
            pdf_utils.apply_pdf_transcript_json(out_json, pdf_path, out_json)
            if srt_path.exists():
                pdf_utils.write_timestamped_transcript(pdf_path, str(srt_path), "transcript.txt")
        except Exception as exc:
            print(f"⚠️  PDF transcript failed: {exc}")

    try:
        segmentation.json_to_tsv(out_json, f"{Path(video).stem}.tsv")
    except Exception as exc:
        print(f"⚠️  TSV conversion failed: {exc}")

    segs = json.loads(Path(out_json).read_text())["segments"]
    with open("markup_guide.txt", "w") as g:
        for seg in segs:
            start, end = round(seg["start"], 2), round(seg["end"], 2)
            if diarize:
                speaker = seg.get("label") or seg.get("speaker", "SPEAKER")
            else:
                speaker = "SPEAKER"
            text = seg["text"].strip().replace("\n", " ")
            g.write(f"[{start}-{end}] {speaker}: {text}\n")
    print("✅  markup_guide.txt ready – edit ranges or use TSV workflow")

__all__ = ["transcribe", "compute_type", "is_apple_silicon"]

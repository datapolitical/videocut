"""Transcription utilities using WhisperX."""
from __future__ import annotations
import json
import platform
import subprocess
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import requests

from . import pdf_utils, segmentation

load_dotenv()

_BASE_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_WHISPER_BIN = _BASE_DIR / "tools/whisper/whisper"
_DEFAULT_MODEL = _BASE_DIR / "tools/models/ggml-small.en-q8.bin"


def _run(cmd: list[str]) -> None:
    """Run subprocess command and exit on failure."""
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - passthrough
        raise SystemExit(exc.returncode) from exc


def _ensure_model(model: Path) -> None:
    """Download Whisper model from Hugging Face if missing."""
    if model.exists():
        return
    model.parent.mkdir(parents=True, exist_ok=True)
    url = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en-q8_0.bin"
    print(f"[videocut] Downloading model → {model} …")
    with requests.get(url, stream=True) as r:  # pragma: no cover - network
        r.raise_for_status()
        with open(model, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def _transcribe_whispercpp(video: str, whisper_bin: Path = _DEFAULT_WHISPER_BIN, model: Path = _DEFAULT_MODEL) -> None:
    """Transcribe *video* using whisper.cpp."""
    base_stem = Path(video).stem
    wav_path = Path(f"{base_stem}.wav")
    _run([
        "ffmpeg",
        "-y",
        "-i",
        video,
        "-ac",
        "1",
        "-ar",
        "16000",
        str(wav_path),
    ])
    _ensure_model(model)
    _run([
        str(whisper_bin),
        "-m",
        str(model),
        "-f",
        str(wav_path),
        "-osrt",
        "-of",
        base_stem,
    ])
    wav_path.unlink(missing_ok=True)


def is_apple_silicon() -> bool:
    """Return True if running on Apple Silicon."""
    return platform.system() == "Darwin" and platform.machine() in {"arm64", "arm"}


def compute_type() -> str:
    """Return compute_type argument for WhisperX based on architecture."""
    return "float32" if is_apple_silicon() else "float16"


def transcribe_with_mlx(video_path: str) -> str:
    import mlx_whisper
    import tempfile
    import subprocess
    import os

    # Convert audio to 16kHz mono WAV for mlx-whisper
    wav_path = tempfile.mktemp(suffix=".wav")
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav_path
    ], check=True)

    model = mlx_whisper.Whisper("tiny")  # valid options: tiny, base, small, medium, large
    result = model.transcribe(wav_path)

    os.unlink(wav_path)
    return result["text"]



def transcribe(
    video: str,
    hf_token: str | None = None,
    diarize: bool = False,
    speaker_db: str | None = None,
    progress: bool = True,
    pdf_path: str | None = None,
    backend: str = "whisperx",
) -> None:
    """Run WhisperX on *video* and produce ``markup_guide.txt``.

    If ``speaker_db`` is provided, diarized speaker labels will be mapped to real
    names using embeddings after transcription. Set ``progress`` to ``False`` to
    suppress the WhisperX progress output.
    """
    if backend == "whispercpp":
        print("[INFO] Using whisper.cpp backend")
        _transcribe_whispercpp(video)
        return
    if backend == "mlx":
        print("[INFO] Using mlx-whisper backend")
        result = transcribe_with_mlx(video)
        with open("markup_guide.txt", "w") as f:
            f.write(result)
        return
    try:  # pragma: no cover - optional heavy deps may be missing
        import torch  # noqa: F401
        import whisperx  # noqa: F401
    except ModuleNotFoundError:  # pragma: no cover - graceful fallback
        torch = None
        whisperx = None

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
                pdf_utils.write_timestamped_transcript(
                    pdf_path,
                    str(srt_path),
                    "transcript.txt",
                    json_path=out_json,
                )
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

"""videocut CLI sub-command: **transcribe**

Default behaviour → **whisper.cpp (static) with the small English quantised model**
    * binary:  tools/whisper/whisper
    * model:   tools/models/ggml-small.en-q8.bin

Legacy CPU-only route (Python **whisperx**) is still available via **--cpu-only**.

Usage examples
--------------
```bash
# GPU / Metal path (default)
videocut transcribe videos/May_Test/video.mp4

# Force whisperx (CPU-only, useful on Intel Macs / CI boxes)
videocut transcribe videos/May_Test/video.mp4 --cpu-only
```
The command produces `video.srt` and `video.txt` in the working directory.  Use
`--keep-wav` if you want to retain the intermediate 16 kHz WAV.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List

import click


_BASE_DIR = Path(__file__).resolve().parent.parent.parent
_DEFAULT_WHISPER_BIN = _BASE_DIR / "tools/whisper/whisper"
_DEFAULT_MODEL = _BASE_DIR / "tools/models/ggml-small.en-q8.bin"


def _run(cmd: List[str]) -> None:
    """Run *cmd* via subprocess.run with immediate error reporting."""
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc


def _transcribe_whisper_cpp(
    wav_path: Path,
    base_stem: str,
    whisper_bin: Path,
    model: Path,
) -> None:
    """Invoke whisper.cpp binary to create subtitles and text."""
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


def _transcribe_whisperx(wav_path: Path, base_stem: str) -> None:
    """CPU-only fallback using Python whisperx (must be installed)."""
    try:
        import whisperx  # type: ignore
    except ModuleNotFoundError as err:
        click.echo("[videocut] whisperx not installed – run `pip install whisperx`.")
        raise SystemExit(1) from err

    model = whisperx.load_model("small.en", device="cpu")
    audio = whisperx.load_audio(str(wav_path))
    result = model.transcribe(audio)

    text_path = Path(f"{base_stem}.txt")
    srt_path = Path(f"{base_stem}.srt")

    text_path.write_text(result["text"], encoding="utf-8")
    with srt_path.open("w", encoding="utf-8") as srt_f:
        for i, seg in enumerate(result["segments"], 1):
            start = seg["start"]
            end = seg["end"]
            srt_f.write(f"{i}\n{_fmt_ts(start)} --> {_fmt_ts(end)}\n{seg['text'].strip()}\n\n")


def _fmt_ts(seconds: float) -> str:
    """Format *seconds* as SRT HH:MM:SS,mmm."""
    ms = int(seconds * 1000)
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


@click.command("transcribe")
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--model",
    "-m",
    default=_DEFAULT_MODEL,
    show_default=True,
    help="Path to whisper.cpp model file (*.bin)",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--whisper-bin",
    "-w",
    default=_DEFAULT_WHISPER_BIN,
    show_default=True,
    help="Path to whisper.cpp executable",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--cpu-only/--gpu",
    default=False,
    help="Use legacy Python whisperx on CPU instead of whisper.cpp",
)
@click.option(
    "--keep-wav/--no-keep-wav",
    default=False,
    show_default=True,
    help="Keep the temporary 16 kHz WAV",
)
@click.option(
    "--ffmpeg-bin",
    default="ffmpeg",
    show_default=True,
    help="ffmpeg executable (override if not on PATH)",
)
def transcribe(
    input_file: Path,
    model: Path,
    whisper_bin: Path,
    cpu_only: bool,
    keep_wav: bool,
    ffmpeg_bin: str,
) -> None:
    """Convert *INPUT_FILE* to text + SRT via whisper.cpp (default) or whisperx."""
    base_stem = input_file.stem
    wav_path = Path(f"{base_stem}.wav")

    click.echo(f"[videocut] Extracting mono 16 kHz audio → {wav_path} …")
    _run([
        ffmpeg_bin,
        "-y",
        "-i",
        str(input_file),
        "-ac",
        "1",
        "-ar",
        "16000",
        str(wav_path),
    ])

    if cpu_only:
        click.echo("[videocut] Using whisperx (CPU)…")
        _transcribe_whisperx(wav_path, base_stem)
    else:
        click.echo("[videocut] Using whisper.cpp …")
        _transcribe_whisper_cpp(wav_path, base_stem, whisper_bin, model)

    if not keep_wav:
        wav_path.unlink(missing_ok=True)
        click.echo("[videocut] Cleaned up temporary WAV.")

    click.echo("[videocut] Transcription complete → " f"{base_stem}.srt / {base_stem}.txt")


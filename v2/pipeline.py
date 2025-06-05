#!/usr/bin/env python3
"""pipeline.py - Audio-first video clipping pipeline (v2).

This script mirrors the functionality of :mod:`videocut.cli.steps.run_pipeline`
but avoids fully downloading the source video. Instead it:

1. Downloads *audio only* using ``yt-dlp``.
2. Runs WhisperX transcription/diarization on the audio file.
3. Identifies clip segments via ``markup_guide.txt``.
4. Redownloads only the required video sections with
   ``yt-dlp --download-sections`` and builds polished clips.
5. Optionally concatenates the clips into a final video.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from videocut.core.clip_utils import _build_faded_clip

load_dotenv()

# ────────────────────────────── CONSTANTS ─────────────────────────────
WHITE_FLASH_SEC = 0.5
FADE_SEC = 0.5
TARGET_W, TARGET_H = 1280, 720
TARGET_FPS = 30


# ────────────────────────────── HELPERS ──────────────────────────────

def is_apple_silicon() -> bool:
    """Return True when running on Apple Silicon."""
    return platform.system() == "Darwin" and platform.machine() in {"arm64", "arm"}


def seconds_to_timestamp(sec: float) -> str:
    """Return hh:mm:ss.mmm timestamp for yt-dlp."""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


# ──────────────────────────── AUDIO DOWNLOAD ─────────────────────────

def download_audio(url: str, out_file: str = "input_audio.m4a") -> str:
    """Download audio only from *url* using yt-dlp."""
    subprocess.run(["yt-dlp", "-f", "bestaudio", "-o", out_file, url], check=True)
    return out_file


# ────────────────────────────── TRANSCRIBE ───────────────────────────

def transcribe(audio_file: str, hf_token: str | None, diarize: bool) -> None:
    """Run WhisperX on *audio_file* and write ``markup_guide.txt``."""
    compute_type = "float32" if is_apple_silicon() else "float16"
    out_json = f"{Path(audio_file).stem}.json"

    cmd = ["whisperx", audio_file, "--compute_type", compute_type, "--output_dir", "."]
    if diarize:
        if not hf_token:
            sys.exit("❌  --diarize requires --hf_token or HF_TOKEN env var")
        cmd += ["--diarize", "--hf_token", hf_token]

    print("🧠  WhisperX …")
    subprocess.run(cmd, check=True)
    if not Path(out_json).exists():
        sys.exit(f"❌  Expected {out_json} not found")

    data = json.loads(Path(out_json).read_text())
    with open("markup_guide.txt", "w") as g:
        for seg in data["segments"]:
            s, e = round(seg["start"], 2), round(seg["end"], 2)
            spk = seg.get("speaker", "SPEAKER") if diarize else "SPEAKER"
            txt = seg["text"].strip().replace("\n", " ")
            g.write(f"[{s}–{e}] {spk}: {txt}\n")
    print("✅  markup_guide.txt ready – mark your segments")

def extract_marked(markup: str = "markup_guide.txt", out_json: str = "segments_to_keep.json") -> None:
    if not Path(markup).exists():
        sys.exit(f"❌  '{markup}' not found – run --transcribe first")
    segs, open_start = [], None
    for ln, line in enumerate(Path(markup).read_text().splitlines(), 1):
        line = line.strip()
        if line.startswith("[") and "–" in line:
            ts = line.split("]")[0][1:].replace("–", "-")
            try:
                s, e = map(float, ts.split("-"))
                segs.append({"start": s, "end": e})
            except ValueError:
                print(f"⚠️  bad timestamp on line {ln}")
        elif line.startswith("START ["):
            open_start = float(line[line.find("[")+1:line.find("-")])
        elif line.startswith("END [") and open_start is not None:
            end = float(line[line.find("-")+1:line.find("]")])
            segs.append({"start": open_start, "end": end})
            open_start = None
    Path(out_json).write_text(json.dumps(segs, indent=2))
    print(f"✅  {len(segs)} segment(s) → {out_json}")


# ──────────────────────── FADE/PAD RE‑ENCODE HELPER ─────────────────────────


# ─────────────────────────────── CLIPPER ──────────────────────────────

def generate_clips(url: str, seg_json: str = "segments_to_keep.json", out_dir: str = "clips") -> None:
    if not Path(seg_json).exists():
        sys.exit("❌  segments_to_keep.json missing – run identification step")

    segs = json.loads(Path(seg_json).read_text())
    Path(out_dir).mkdir(exist_ok=True)

    for idx, seg in enumerate(segs):
        start_hms = seconds_to_timestamp(seg["start"])
        end_hms = seconds_to_timestamp(seg["end"])
        section = f"*{start_hms}-{end_hms}"
        raw_path = Path(out_dir) / f"raw_{idx:03d}.%(ext)s"
        print(f"📥  Downloading segment {start_hms}-{end_hms}")
        subprocess.run([
            "yt-dlp", url,
            "--download-sections", section,
            "-o", str(raw_path)
        ], check=True)

        downloaded = next(raw_path.parent.glob(f"raw_{idx:03d}.*"))
        final = Path(out_dir) / f"clip_{idx:03d}.mp4"
        print(f"🎬  Building clip_{idx:03d}.mp4")
        _build_faded_clip(downloaded, final)
        downloaded.unlink()

    print(f"✅  {len(segs)} polished clip(s) → {out_dir}/")


# ─────────────────────────────── CONCAT ──────────────────────────────

def concatenate_clips(clips_dir: str = "clips", out_file: str = "final_video.mp4") -> None:
    clips = sorted(Path(clips_dir).glob("clip_*.mp4"))
    if not clips:
        sys.exit("❌  No clips – run generate-clips first")

    w, h = map(str, subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
        "-of", "csv=p=0", str(clips[0])
    ], text=True).strip().split(','))

    inputs = []
    for idx, c in enumerate(clips):
        inputs += ["-i", str(c)]
        if idx < len(clips) - 1:
            inputs += ["-f", "lavfi", "-i", f"color=white:s={w}x{h}:d={WHITE_FLASH_SEC}"]

    v_n = inputs.count("-i")
    a_n = len(clips)

    v_filter = f"concat=n={v_n}:v=1:a=0[v]"
    a_filter = f"concat=n={a_n}:v=0:a=1[a]"

    subprocess.run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", v_filter + ";" + a_filter,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k", out_file
    ], check=True)

    print(f"🏁  {out_file} assembled ({len(clips)} clips)")


# ──────────────────────────────── CLI ────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser("pipeline_v2")
    p.add_argument("--url", help="Video URL for yt-dlp")
    p.add_argument("--hf_token", default=os.getenv("HF_TOKEN"), help="HuggingFace token for diarization")
    p.add_argument("--download-audio", action="store_true", help="Download audio only")
    p.add_argument("--transcribe", action="store_true", help="Run WhisperX on audio")
    p.add_argument("--diarize", action="store_true", help="Use speaker diarization")
    p.add_argument("--extract-marked", action="store_true", help="Parse markup_guide.txt → segments_to_keep.json")
    p.add_argument("--generate-clips", action="store_true", help="Download segments and build clips")
    p.add_argument("--concatenate", action="store_true", help="Join clips with white flashes")

    args = p.parse_args()

    audio_file = "input_audio.m4a"
    if args.download_audio:
        if not args.url:
            sys.exit("❌  --download-audio needs --url")
        audio_file = download_audio(args.url, audio_file)
    if args.transcribe:
        transcribe(audio_file, args.hf_token, args.diarize)
    if args.extract_marked:
        extract_marked()
    if args.generate_clips:
        if not args.url:
            sys.exit("❌  --generate-clips needs --url")
        generate_clips(args.url)
    if args.concatenate:
        concatenate_clips()

    if not any([
        args.download_audio, args.transcribe,
        args.extract_marked, args.generate_clips, args.concatenate
    ]):
        p.print_help()


if __name__ == "__main__":
    main()

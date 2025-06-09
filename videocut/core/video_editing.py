"""Video editing helpers using FFmpeg."""
from __future__ import annotations
import subprocess
import json
import sys
from pathlib import Path
from typing import List

WHITE_FLASH_SEC = 0.5
FADE_SEC = 0.5
TARGET_W, TARGET_H = 1280, 720
TARGET_FPS = 30


def _build_faded_clip(src: Path, dst: Path) -> None:
    dur = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "format=duration", "-of", "csv=p=0", str(src)
    ], text=True).strip())
    end_time = max(dur - FADE_SEC, 0)

    vf = (
        f"fps={TARGET_FPS},scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"  # noqa
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:color=white,"  # noqa
        f"format=yuv420p,fade=t=in:st=0:d={FADE_SEC},fade=t=out:st={end_time}:d={FADE_SEC}"
    )
    af = f"afade=t=in:st=0:d={FADE_SEC},afade=t=out:st={end_time}:d={FADE_SEC}"

    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(src),
        "-vf", vf, "-af", af,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k", str(dst)
    ], check=True)


def generate_clips_from_segments(
    input_video: str,
    segments: list[dict],
    out_dir: str = "clips",
) -> None:
    """Cut *input_video* into clips based on *segments*."""
    Path(out_dir).mkdir(exist_ok=True)
    for i, seg in enumerate(segments):
        tmp = Path(out_dir) / f"tmp_{i:03d}.mp4"
        final = Path(out_dir) / f"clip_{i:03d}.mp4"
        print(f"🎬  clip_{i:03d}  {seg['start']:.2f}–{seg['end']:.2f}")
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-ss",
                str(seg["start"]),
                "-to",
                str(seg["end"]),
                "-i",
                input_video,
                "-c",
                "copy",
                str(tmp),
            ],
            check=True,
        )
        _build_faded_clip(tmp, final)
        tmp.unlink()
    print(f"✅  {len(segments)} polished clip(s) in {out_dir}/")


def generate_clips(
    input_video: str,
    seg_json: str = "segments_to_keep.json",
    out_dir: str = "clips",
) -> None:
    """Generate clips using a segments JSON file."""
    if not Path(seg_json).exists():
        sys.exit("❌  segments_to_keep.json missing – run clip identification")
    segs = json.loads(Path(seg_json).read_text())
    generate_clips_from_segments(input_video, segs, out_dir)


def concatenate_clips(clips_dir: str = "clips", out_file: str = "final_video.mp4") -> None:
    clips = sorted(Path(clips_dir).glob("clip_*.mp4"))
    if not clips:
        sys.exit("❌  No clips found – run generate_clips first")

    w, h = map(str, subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
        "-of", "csv=p=0", str(clips[0])
    ], text=True).strip().split(','))

    inputs: List[str] = []
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
    print(f"🏁  {out_file} assembled ({len(clips)} clips + white flashes)")

__all__ = [
    "generate_clips_from_segments",
    "generate_clips",
    "concatenate_clips",
]

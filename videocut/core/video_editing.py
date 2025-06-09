"""Video editing helpers using FFmpeg."""
from __future__ import annotations
import subprocess
import json
import sys
from pathlib import Path
from typing import List
from . import segmentation

WHITE_FLASH_SEC = 0.5
FADE_SEC = 0.5
TARGET_W, TARGET_H = 1280, 720
TARGET_FPS = 30


def _parse_time(ts: str) -> float:
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _load_srt_entries(path: Path) -> list[dict]:
    entries: list[dict] = []
    lines = path.read_text().splitlines()
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        if lines[i].startswith("="):
            i += 1
            continue
        number = lines[i].strip()
        i += 1
        if i >= len(lines):
            break
        ts_line = lines[i].strip()
        i += 1
        if "-->" not in ts_line:
            continue
        start_str, end_str = [p.strip() for p in ts_line.split("-->")]
        start, end = _parse_time(start_str), _parse_time(end_str)
        while i < len(lines) and lines[i].strip():
            i += 1
        entries.append({"number": int(number), "start": start, "end": end})
        while i < len(lines) and not lines[i].strip():
            i += 1
    return entries


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


def _segments_from_txt(txt_file: str, srt_file: str) -> list[dict]:
    numbers = segmentation.segments_from_txt(txt_file)
    entries = _load_srt_entries(Path(srt_file))
    idx = {e["number"]: e for e in entries}
    segs: list[dict] = []
    for s, e in numbers:
        if s in idx and e in idx:
            segs.append({"start": idx[s]["start"], "end": idx[e]["end"]})
    return segs


def generate_clips(
    input_video: str,
    segments_file: str = "segments_to_keep.json",
    out_dir: str = "clips",
    srt_file: str | None = None,
) -> None:
    """Generate clips from a JSON or text segments file."""
    if not Path(segments_file).exists():
        sys.exit(f"❌  {segments_file} missing – run clip identification")

    if segments_file.endswith(".txt"):
        if srt_file is None:
            srt_file = str(Path(input_video).with_suffix(".srt"))
        if not Path(srt_file).exists():
            sys.exit(f"❌  SRT file '{srt_file}' required for segments.txt")
        segs = _segments_from_txt(segments_file, srt_file)
    else:
        segs = json.loads(Path(segments_file).read_text())

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

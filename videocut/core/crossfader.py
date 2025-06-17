"""Concatenate clips with optional dip-to-color transitions."""
from __future__ import annotations

from pathlib import Path
import subprocess

from . import video_editing


def concat_default(clips_dir: str, output_path: str) -> None:
    """Concatenate using the standard white-flash transitions."""
    video_editing.concatenate_clips(clips_dir, output_path)


def concat_with_dip(
    clips_dir: str,
    output_path: str,
    dip_color: str = "#AAAAAA",
    fade_dur: float = 0.25,
    hold_dur: float = 0.1,
) -> None:
    """Concatenate clips with a dip-to-color between each clip."""
    # Convert color format "#FFFFFF" -> "0xFFFFFF"
    if dip_color.startswith("#"):
        dip_color = "0x" + dip_color[1:]

    clips = sorted(Path(clips_dir).glob("clip_*.mp4"))
    if len(clips) < 2:
        raise ValueError("At least two clips are required for dip transition.")

    inputs: list[str] = []
    filters: list[str] = []
    durations: list[float] = []
    for clip in clips:
        inputs += ["-i", str(clip)]
        dur = float(
            subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "csv=p=0",
                    str(clip),
                ],
                text=True,
            ).strip()
        )
        durations.append(dur)

    parts: list[str] = []

    for i, dur in enumerate(durations):
        vfilter = f"[{i}:v]format=yuv420p,setpts=PTS-STARTPTS"
        if i > 0:
            vfilter += f",fade=t=in:st=0:d={fade_dur}:c={dip_color}"
        if i < len(clips) - 1:
            start = max(dur - fade_dur, 0)
            vfilter += f",fade=t=out:st={start}:d={fade_dur}:c={dip_color}"
        vfilter += f"[v{i}f]"
        filters.append(vfilter)
        filters.append(f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]")
        parts.append(f"[v{i}f][a{i}]")

    chain = "".join(parts)
    filters.append(f"{chain}concat=n={len(clips)}:v=1:a=1[outv][outa]")

    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[outv]",
        "-map",
        "[outa]",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        output_path,
    ]

    subprocess.run(cmd, check=True)


__all__ = ["concat_default", "concat_with_dip"]

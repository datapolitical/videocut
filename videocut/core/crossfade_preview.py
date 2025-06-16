"""Generate crossfade previews between the first two clips.

This helper creates a series of videos showing different fade lengths and
brightness adjustments between the first two clips in a directory.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List


def preview_crossfades(clips_dir: str = "clips", out_dir: str = "fade_previews") -> None:
    """Generate sample crossfades using FFmpeg.

    Parameters
    ----------
    clips_dir:
        Directory containing ``clip_000.mp4`` and ``clip_001.mp4``.
    out_dir:
        Directory where the preview files will be written.
    """
    c1 = Path(clips_dir) / "clip_000.mp4"
    c2 = Path(clips_dir) / "clip_001.mp4"
    if not c1.exists() or not c2.exists():
        raise FileNotFoundError("clip_000.mp4 or clip_001.mp4 missing")

    Path(out_dir).mkdir(exist_ok=True)

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
                str(c1),
            ],
            text=True,
        ).strip()
    )

    brightness: List[float] = [0.5 + 0.05 * i for i in range(20)]
    lengths: List[float] = [0.25 + 0.1 * i for i in range(20)]

    for i, (b, d) in enumerate(zip(brightness, lengths)):
        offset = max(dur - d, 0)
        vf = (
            f"[0:v]format=yuv420p,setpts=PTS-STARTPTS[v0];"
            f"[1:v]format=yuv420p,eq=brightness={b-1.0},setpts=PTS-STARTPTS[v1];"
            f"[v0][v1]xfade=transition=fade:duration={d}:offset={offset}[v]"
        )
        af = f"[0:a][1:a]acrossfade=d={d}[a]"
        out = Path(out_dir) / f"fade_{i:02d}.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(c1),
                "-i",
                str(c2),
                "-filter_complex",
                vf + ";" + af,
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                str(out),
            ],
            check=True,
        )
        print(f"✅  {out.name} duration={d:.2f}s brightness={b:.2f}")


__all__ = ["preview_crossfades"]

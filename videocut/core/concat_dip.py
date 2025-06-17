import subprocess
import tempfile
import ffmpeg
import glob
from pathlib import Path


def concatenate_with_dip_fast(clips_dir: str, out_path: str) -> None:
    clips = sorted(Path(clips_dir).glob("clip_*.mp4"))
    assert len(clips) >= 2, "Need at least two clips for dip-fast transition"

    inputs = []
    durations = []
    fade_duration = 0.015

    for i, clip in enumerate(clips):
        probe = ffmpeg.probe(str(clip))
        vstream = next(s for s in probe["streams"] if s["codec_type"] == "video")
        astream = next(s for s in probe["streams"] if s["codec_type"] == "audio")

        if vstream["r_frame_rate"] != "30/1":
            raise ValueError(f"{clip} is not 30fps")
        if vstream["width"] != 1280 or vstream["height"] != 720:
            raise ValueError(f"{clip} is not 1280x720")
        if astream["sample_rate"] != "44100":
            raise ValueError(f"{clip} audio is not 44100Hz")

        dur = float(vstream.get("duration", vstream.get("tags", {}).get("DURATION", 0)))
        durations.append(dur)
        inputs.extend(["-i", str(clip)])

    vf_filters = []
    af_filters = []
    vlabels = []
    alabels = []

    for i, dur in enumerate(durations):
        v_in = f"[{i}:v]"
        a_in = f"[{i}:a]"

        if i < len(durations) - 1:
            fade_out = f"{v_in}fade=t=out:st={round(dur - fade_duration, 3)}:d={fade_duration}:c=white[v{i}]"
            fade_in = f"[{i + 1}:v]fade=t=in:st=0:d={fade_duration}:c=white[v{i+1}]"
            vf_filters.append(fade_out)
            vf_filters.append(fade_in)
            vlabels.extend([f"[v{i}]", f"[v{i+1}]"])
            alabels.extend([a_in, f"[{i+1}:a]"])
        else:
            # Last video, just passthrough
            vf_filters.append(f"{v_in}setpts=PTS-STARTPTS[v{i}]")
            vlabels.append(f"[v{i}]")
            alabels.append(a_in)

    v_concat = "".join(vlabels)
    a_concat = "".join(alabels)
    vf_filters.append(f"{v_concat}concat=n={len(clips)}:v=1:a=0[outv]")
    af_filters.append(f"{a_concat}concat=n={len(clips)}:v=0:a=1[outa]")

    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        ";".join(vf_filters + af_filters),
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "128k",
        out_path
    ]

    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

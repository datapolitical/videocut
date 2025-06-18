"""Video editing helpers using FFmpeg."""
from __future__ import annotations
import subprocess
import json
import sys
import re
from pathlib import Path
from typing import List
from . import segmentation, alignment

# White flash timing
WHITE_FADE_IN_SEC = 0.2
WHITE_HOLD_SEC = 0.0
WHITE_FADE_OUT_SEC = 0.2
WHITE_FLASH_SEC = WHITE_FADE_IN_SEC + WHITE_HOLD_SEC + WHITE_FADE_OUT_SEC

# Clip fade timing
FADE_SEC = 0.033      # 1-frame fade in & out
TARGET_W, TARGET_H = 1280, 720
TARGET_FPS = 30
BUFFER_SEC = 10.0


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
        "-r", str(TARGET_FPS), "-vsync", "cfr",
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


def _segments_with_text(txt_file: str) -> list[dict]:
    """Return list of segments with joined text.

    Supports the original ``[NUMBER] text`` format as well as the new
    tab-separated ``SPEAKER\t[START-END]\tTEXT`` layout produced by the
    ``segmenter`` module.
    """

    segs: list[dict] = []
    start_num: int | None = None
    end_num: int | None = None
    start_ts: float | None = None
    end_ts: float | None = None
    lines: list[str] = []

    pat_new = re.compile(
        r"^\t?(?P<speaker>[^\t]+)\t\[(?P<start>[\d\.]+)\s*-\s*(?P<end>[\d\.]+)\]\t(?P<text>.*)"
    )
    pat_old_ts = re.compile(
        r"^\t?\[(?P<start>[\d\.]+)\s*-\s*(?P<end>[\d\.]+)\]\s*(?P<rest>.*)"
    )
    pat_old_num = re.compile(r"^\t?\[(?P<num>\d+)\](?P<rest>.*)")

    for raw in Path(txt_file).read_text().splitlines():
        line = raw.strip("\n")
        if line == "=START=":
            start_num = end_num = None
            start_ts = end_ts = None
            lines = []
            continue
        if line == "=END=":
            if lines:
                seg: dict = {"text": " ".join(lines)}
                if start_num is not None:
                    seg["start_num"] = start_num
                    seg["end_num"] = end_num if end_num is not None else start_num
                if start_ts is not None:
                    seg["start"] = start_ts
                    seg["end"] = end_ts if end_ts is not None else start_ts
                segs.append(seg)
            start_num = end_num = None
            start_ts = end_ts = None
            lines = []
            continue

        m_new = pat_new.match(line.lstrip())
        if m_new:
            speaker = m_new.group("speaker").strip()
            s = float(m_new.group("start"))
            e = float(m_new.group("end"))
            txt = m_new.group("text").strip()
            if start_ts is None:
                start_ts = s
            end_ts = e
            lines.append(f"{speaker}: {txt}")
            continue

        m_old_ts = pat_old_ts.match(line.lstrip())
        if m_old_ts:
            s = float(m_old_ts.group("start"))
            e = float(m_old_ts.group("end"))
            rest = m_old_ts.group("rest").strip()
            if start_ts is None:
                start_ts = s
            end_ts = e
            lines.append(rest)
            continue

        m_old_num = pat_old_num.match(line.lstrip())
        if m_old_num:
            num = int(m_old_num.group("num"))
            rest = m_old_num.group("rest").strip()
            if start_num is None:
                start_num = num
            end_num = num
            lines.append(rest)
            continue

    return segs


def generate_and_align(
    input_video: str,
    segments_file: str = "segments_to_keep.json",
    out_dir: str = "clips",
    srt_file: str | None = None,
) -> None:
    """Generate clips from a JSON or text segments file."""
    if not Path(segments_file).exists():
        sys.exit(f"❌  {segments_file} missing – run clip identification")

    if segments_file.endswith(".txt"):
        parsed = _segments_with_text(segments_file)

        # new timestamp-based format
        if parsed and "start" in parsed[0]:
            final: list[dict] = []
            timestamps: dict = {}
            Path(out_dir).mkdir(exist_ok=True)
            for i, seg in enumerate(parsed):
                orig_start = seg["start"]
                orig_end = seg["end"]
                buf_start = max(0.0, orig_start - BUFFER_SEC)
                buf_end = orig_end + BUFFER_SEC

                buf_path = Path(out_dir) / f"buffer_{i:03d}.mp4"
                subprocess.run([
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-ss",
                    str(buf_start),
                    "-to",
                    str(buf_end),
                    "-i",
                    input_video,
                    "-c",
                    "copy",
                    str(buf_path),
                ], check=True)

                txt_path = Path(out_dir) / f"clip_{i:03d}_snippet.txt"
                txt_path.write_text(seg["text"] + "\n")
                aligned_json = Path(out_dir) / f"clip_{i:03d}_aligned.json"
                alignment.align_with_transcript(
                    str(buf_path), str(txt_path), str(aligned_json)
                )

                words = json.loads(aligned_json.read_text())
                if words:
                    rel_start = float(words[0]["start"])
                    rel_end = float(words[-1]["end"])
                else:
                    rel_start = 0.0
                    rel_end = buf_end - buf_start

                abs_start = buf_start + rel_start
                abs_end = buf_start + rel_end

                final.append({"start": abs_start, "end": abs_end})
                timestamps[f"clip_{i:03d}"] = {
                    "original": {
                        "start": f"{orig_start:.3f}",
                        "end": f"{orig_end:.3f}",
                    },
                    "aligned": {
                        "start": f"{abs_start:.3f}",
                        "end": f"{abs_end:.3f}",
                    },
                }

                buf_path.unlink(missing_ok=True)
                txt_path.unlink(missing_ok=True)

            if final:
                generate_clips_from_segments(input_video, final, out_dir)
                Path(out_dir, "timestamps.json").write_text(
                    json.dumps(timestamps, indent=2)
                )
        else:
            if srt_file is None:
                srt_file = str(Path(input_video).with_suffix(".srt"))
            if not Path(srt_file).exists():
                sys.exit(f"❌  SRT file '{srt_file}' required for segments.txt")

            entries = _load_srt_entries(Path(srt_file))
            idx = {e["number"]: e for e in entries}

            final: list[dict] = []
            timestamps: dict = {}
            Path(out_dir).mkdir(exist_ok=True)
            for i, seg in enumerate(parsed):
                if seg.get("start_num") not in idx or seg.get("end_num") not in idx:
                    continue
                orig_start = idx[seg["start_num"]]["start"]
                orig_end = idx[seg["end_num"]]["end"]
                buf_start = max(0.0, orig_start - BUFFER_SEC)
                buf_end = orig_end + BUFFER_SEC

                buf_path = Path(out_dir) / f"buffer_{i:03d}.mp4"
                subprocess.run([
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-ss",
                    str(buf_start),
                    "-to",
                    str(buf_end),
                    "-i",
                    input_video,
                    "-c",
                    "copy",
                    str(buf_path),
                ], check=True)

                txt_path = Path(out_dir) / f"clip_{i:03d}_snippet.txt"
                txt_path.write_text(seg["text"] + "\n")
                aligned_json = Path(out_dir) / f"clip_{i:03d}_aligned.json"
                alignment.align_with_transcript(
                    str(buf_path), str(txt_path), str(aligned_json)
                )

                words = json.loads(aligned_json.read_text())
                if words:
                    rel_start = float(words[0]["start"])
                    rel_end = float(words[-1]["end"])
                else:
                    rel_start = 0.0
                    rel_end = buf_end - buf_start

                abs_start = buf_start + rel_start
                abs_end = buf_start + rel_end

                final.append({"start": abs_start, "end": abs_end})
                timestamps[f"clip_{i:03d}"] = {
                    "original": {
                        "start": f"{orig_start:.3f}",
                        "end": f"{orig_end:.3f}",
                    },
                    "aligned": {
                        "start": f"{abs_start:.3f}",
                        "end": f"{abs_end:.3f}",
                    },
                }

                buf_path.unlink(missing_ok=True)
                txt_path.unlink(missing_ok=True)

        if final:
            generate_clips_from_segments(input_video, final, out_dir)
            Path(out_dir, "timestamps.json").write_text(json.dumps(timestamps, indent=2))
    else:
        segs = json.loads(Path(segments_file).read_text())
        generate_clips_from_segments(input_video, segs, out_dir)


def clip_segments(
    input_video: str,
    segments_file: str = "segments_to_keep.json",
    out_dir: str = "clips",
    srt_file: str | None = None,
) -> None:
    """Generate clips exactly as specified in the segments file."""
    if not Path(segments_file).exists():
        sys.exit(f"❌  {segments_file} missing – run clip identification")

    if segments_file.endswith(".txt"):
        parsed = _segments_with_text(segments_file)
        if parsed and "start" in parsed[0]:
            segs = [{"start": seg["start"], "end": seg["end"]} for seg in parsed]
        else:
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
        sys.exit("❌  No clips found – run generate-and-align or clip first")

    w, h = map(str, subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
        "-of", "csv=p=0", str(clips[0])
    ], text=True).strip().split(','))

    inputs: List[str] = []
    for idx, c in enumerate(clips):
        inputs += ["-i", str(c)]
        if idx < len(clips) - 1:
            flash_filter = (
                f"color=c=0xfafafa:s={w}x{h}:d={WHITE_FLASH_SEC},"
                f"format=yuva420p,"
                f"split[base][alpha];"
                f"[alpha]"
                f"geq=lum='255*if(lt(T,{WHITE_FADE_IN_SEC}),"
                f"pow(T/{WHITE_FADE_IN_SEC},2),"
                f"if(lt(T,{WHITE_FADE_IN_SEC + WHITE_HOLD_SEC}),"
                f"1,"
                f"pow((1 - (T - {WHITE_FADE_IN_SEC + WHITE_HOLD_SEC}) / {WHITE_FADE_OUT_SEC}),2)"
                f"))'[alpha];"
                f"[base][alpha]alphamerge"
            )
            inputs += ["-f", "lavfi", "-i", flash_filter]

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
    "generate_and_align",
    "clip_segments",
    "concatenate_clips",
]

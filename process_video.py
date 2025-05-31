#!/usr/bin/env python3
import os
import sys
import json
import argparse
import subprocess
from pathlib import Path

# ─── WhisperX / Pyannote imports ────────────────────────────────────────────────────
import whisperx
from whisperx import load_align_model, align
from whisperx.audio import load_audio
from whisperx.diarization import DiarizationPipeline


# ─── CONSTANTS ─────────────────────────────────────────────────────────────────────
WHITE_FADE_DURATION = 0.5  # seconds of white screen between clips


def transcribe_and_optionally_diarize(
    audio_path: str,
    hf_token: str,
    do_diarize: bool,
    device: str = "cpu",
    model_size: str = "large-v2",
):
    """
    1) Run WhisperX transcription → alignment
    2) (Optionally) run speaker diarization
    Outputs:
      • transcript.json            — raw WhisperX output
      • transcript_aligned.json    — word‐aligned transcript
      • transcript_diarized.json   — if do_diarize=True
    """
    print(f"🔊 Transcribing “{audio_path}” with WhisperX (model={model_size}, device={device}) …")

    # ─── Step 1: Load model & transcribe ────────────────────────────────────────────
    wx_model = whisperx.load_model(model_size, device=device)
    result = wx_model.transcribe(audio_path)
    with open("transcript.json", "w") as f:
        json.dump(result, f, indent=2)
    print("✅ Raw transcript saved to transcript.json")

    # ─── Step 2: Word‐level alignment ───────────────────────────────────────────────
    audio_data = load_audio(audio_path, sr=16000)  # 1D numpy array
    align_model, metadata = load_align_model(
        language_code=result["language"], device=device
    )
    result_aligned = align_model.align(
        result["segments"],  # WhisperX’s segment list
        audio_data,
        align_model,
        metadata,
        device=device,
    )
    with open("transcript_aligned.json", "w") as f:
        json.dump(result_aligned, f, indent=2)
    print("✅ Aligned transcript saved to transcript_aligned.json")

    # ─── Step 3: (Optional) Speaker diarization ────────────────────────────────────
    if do_diarize:
        if hf_token is None:
            print("❗ You must supply --hf_token to run diarization.")
            sys.exit(1)

        print("🔊 Running speaker diarization with WhisperX’s wrapper …")
        diarize_model = DiarizationPipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1", use_auth_token=hf_token, device=device
        )
        diarization = diarize_model(audio_path)

        from whisperx import save_diarization

        result_diarized = save_diarization(result_aligned, diarization)
        with open("transcript_diarized.json", "w") as f:
            json.dump(result_diarized, f, indent=2)
        print("✅ Diarized transcript saved to transcript_diarized.json")


def extract_marked_segments(markup_path: str):
    """
    Reads “markup_guide.txt” for lines like “[START–END] …”, extracts all (start, end)
    pairs, and writes them into segments_to_keep.json.
    """
    if not os.path.exists(markup_path):
        print(f"❌ Error: cannot find “{markup_path}”.")
        sys.exit(1)

    segments = []
    with open(markup_path, "r") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if line.startswith("[") and "–" in line:
                try:
                    ts = line.split("]")[0][1:]
                    start_str, end_str = ts.split("–")
                    start = float(start_str)
                    end = float(end_str)
                    segments.append((start, end))
                except Exception:
                    print(f"⚠️ Skipping malformed timestamp on line {lineno}: {line}")

    with open("segments_to_keep.json", "w") as outf:
        json.dump({"segments": segments}, outf, indent=2)

    print(f"✅ Total segments extracted: {len(segments)}")
    print("✅ Wrote segments_to_keep.json")


def generate_clips(input_video: str, segments_json: str = "segments_to_keep.json"):
    """
    For each (start, end) in segments_to_keep.json, extract a clip. Saves as clips/clip_###.mp4.
    (We no longer insert white flashes here—that’s handled in concatenate_clips().)
    """
    if not os.path.exists(segments_json):
        print(f"❌ Error: “{segments_json}” not found. Run --extract-marked first.")
        sys.exit(1)

    with open(segments_json, "r") as f:
        data = json.load(f)
    segments = data.get("segments", [])
    if not segments:
        print("⚠️ No segments found. Nothing to clip.")
        return

    os.makedirs("clips", exist_ok=True)

    # Just extract each segment into clip_###.mp4
    for idx, (start, end) in enumerate(segments):
        clip_path = f"clips/clip_{idx:03d}.mp4"
        print(f"🎬 Creating {clip_path} from {start:.3f} to {end:.3f} …")
        subprocess.run(
            [
                "ffmpeg",
                "-ss",
                f"{start:.3f}",
                "-to",
                f"{end:.3f}",
                "-i",
                input_video,
                "-c:v",
                "copy",
                "-c:a",
                "copy",
                "-y",
                clip_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )


def concatenate_clips():
    """
    Concatenate all clips/clip_###.mp4 into final_output.mp4, inserting a half‐second
    white flash between each pair of clips.
    """
    clip_files = sorted(Path("clips").glob("clip_*.mp4"))
    if not clip_files:
        print("❌ No clips/clip_*.mp4 found. Run --generate-clips first.")
        return

    # ─── Step 1: Probe the resolution of the first clip ──────────────────────────────
    first_clip = str(clip_files[0])
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "json",
            first_clip,
        ],
        capture_output=True,
        text=True,
    )
    info = json.loads(probe.stdout)
    width = info["streams"][0]["width"]
    height = info["streams"][0]["height"]
    print(f"📐 Detected resolution: {width}x{height}")

    # ─── Step 2: Create a single “white flash” clip for half a second ───────────────
    white_clip = "clips/white_flash.mp4"
    if not os.path.exists(white_clip):
        print(f"🎨 Creating a 0.5s white-screen clip at {width}x{height} …")
        subprocess.run(
            [
                "ffmpeg",
                "-f",
                "lavfi",
                "-i",
                f"color=white:s={width}x{height}",
                "-t",
                f"{WHITE_FADE_DURATION}",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-y",
                white_clip,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )

    # ─── Step 3: Build a concat list, interleaving clip_i, white_flash, clip_{i+1}, … ───
    concat_list = "clips/concat_list.txt"
    with open(concat_list, "w") as f:
        for idx, clip_path in enumerate(clip_files):
            f.write(f"file '{clip_path.as_posix()}'\n")
            # After every clip except the last: insert white flash
            if idx < len(clip_files) - 1:
                f.write(f"file '{white_clip}'\n")

    # ─── Step 4: Run ffmpeg concat ──────────────────────────────────────────────────
    print(f"🎬 Concatenating {len(clip_files)} clips + white flashes → final_output.mp4 …")
    subprocess.run(
        [
            "ffmpeg",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_list,
            "-c",
            "copy",
            "final_output.mp4",
            "-y",
        ],
        check=True,
    )
    print("✅ final_output.mp4 created.")


def main():
    parser = argparse.ArgumentParser(description="Process & splice video by timestamp markers.")
    parser.add_argument("--input", "-i", required=True, help="Input video file (e.g. input.mp4)")
    parser.add_argument("--hf_token", "-t", default=None, help="HF token for pyannote diarization (if needed)")
    parser.add_argument("--diarize", action="store_true", help="Run diarization after transcription")
    parser.add_argument("--transcribe", action="store_true", help="Run WhisperX transcription + alignment")
    parser.add_argument("--extract-marked", action="store_true", help="Extract [START–END] segments from markup_guide.txt")
    parser.add_argument("--generate-clips", action="store_true", help="Generate clips from segments_to_keep.json")
    parser.add_argument("--concatenate", action="store_true", help="Concatenate all clips into final_output.mp4 (with white flashes)")
    args = parser.parse_args()

    # 1) Transcribe & optionally diarize
    if args.transcribe:
        transcribe_and_optionally_diarize(
            args.input, hf_token=args.hf_token, do_diarize=args.diarize, device="cpu"
        )

    # 2) Extract marked segments
    if args.extract_marked:
        extract_marked_segments("markup_guide.txt")

    # 3) Generate per-segment clips (no white flashes here anymore)
    if args.generate_clips:
        if not args.input:
            print("❌ --generate-clips requires --input <video>")
            sys.exit(1)
        generate_clips(args.input)

    # 4) Concatenate all clips, inserting half-second white flashes
    if args.concatenate:
        concatenate_clips()


if __name__ == "__main__":
    main()

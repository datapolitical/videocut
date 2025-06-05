"""Legacy video processing workflow (pre-refactor)."""

import argparse
import os
import platform
import sys
from pathlib import Path
from dotenv import load_dotenv

from videocut.core.transcribe import transcribe
from videocut.core.clip_utils import extract_marked, generate_clips, concatenate_clips

load_dotenv()


def transcribe(input_video, hf_token, use_diarization):
    compute_type = "float32" if is_apple_silicon() else "float16"
    transcript_json = f"{Path(input_video).stem}.json"

    print(f"🧠 Running WhisperX on {input_video} (compute_type={compute_type}, diarization={use_diarization})...")

    cmd = [
        "whisperx", input_video,
        "--compute_type", compute_type,
        "--output_dir", "."
    ]

    if use_diarization:
        if not hf_token:
            print("❌ --diarize requires a Hugging Face token (use --hf_token or .env)")
            sys.exit(1)
        cmd += ["--diarize", "--hf_token", hf_token]

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("❌ WhisperX failed. Check above for error messages.")
        sys.exit(1)

    print("✍️ Writing markup guide...")
    with open(transcript_json, "r") as f:
        data = json.load(f)

    with open("markup_guide.txt", "w") as out:
        for seg in data["segments"]:
            start = round(seg["start"], 2)
            end = round(seg["end"], 2)
            speaker = seg.get("speaker", "UNKNOWN") if use_diarization else "UNKNOWN"
            text = seg["text"].strip().replace("\n", " ")
            out.write(f"[{start}–{end}] {speaker}: {text}\n")

    print("✅ Transcription complete. Edit 'markup_guide.txt' and insert START/END markers.")

def extract_marked(markup_file="markup_guide.txt", out_json="segments_to_keep.json"):
    segments = []
    current_start = None

    with open(markup_file, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("START [") or line.startswith("END ["):
                ts = line[line.index("[")+1:line.index("]")]
                try:
                    start, end = map(float, ts.replace("–", "-").split("-"))
                    if line.startswith("START"):
                        current_start = start
                    elif line.startswith("END") and current_start is not None:
                        segments.append({"start": current_start, "end": end})
                        current_start = None
                except ValueError:
                    print(f"⚠️ Invalid timestamp on line: {line}")

    if current_start is not None:
        print("⚠️ Warning: You have a START with no matching END.")

    with open(out_json, "w") as f:
        json.dump(segments, f, indent=2)

    print(f"✅ Extracted {len(segments)} segments from markup and saved to {out_json}")

def generate_clips(input_video, segments_file="segments_to_keep.json", output_dir="clips"):
    if not os.path.exists(segments_file):
        print(f"❌ '{segments_file}' not found. Run --extract-marked first.")
        return

    with open(segments_file, "r") as f:
        segments = json.load(f)

    os.makedirs(output_dir, exist_ok=True)

    for i, seg in enumerate(segments):
        out_path = os.path.join(output_dir, f"clip_{i}.mp4")
        start = seg["start"]
        end = seg["end"]
        print(f"🎬 Exporting: {start}–{end} → {out_path}")
        subprocess.run([
            "ffmpeg", "-y", "-i", input_video,
            "-ss", str(start), "-to", str(end),
            "-c", "copy", out_path
        ])

    print(f"✅ Clips saved to '{output_dir}/'")

def concatenate_clips(clips_dir="clips", output_file="final_video.mp4"):
    concat_list = "concat_list.txt"
    with open(concat_list, "w") as f:
        for fname in sorted(os.listdir(clips_dir)):
            if fname.endswith(".mp4"):
                f.write(f"file '{os.path.join(clips_dir, fname)}'\n")

    print("🧵 Concatenating clips...")
    subprocess.run([
        "ffmpeg", "-f", "concat", "-safe", "0",
        "-i", concat_list,
        "-c", "copy", output_file
    ])

    print(f"✅ Final video saved to: {output_file}")

# --- CLI ---
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process and splice video by transcript markers"
    )
    parser.add_argument("--input", type=str, default="input.mp4", help="Input video filename")
    parser.add_argument(
        "--hf_token",
        type=str,
        default=os.getenv("HF_TOKEN"),
        help="Hugging Face token (from .env or CLI)",
    )
    parser.add_argument(
        "--diarize",
        action="store_true",
        help="Use speaker diarization (slower, requires token)",
    )
    parser.add_argument("--transcribe", action="store_true", help="Transcribe with WhisperX")
    parser.add_argument(
        "--extract-marked",
        action="store_true",
        help="Parse START/END-marked lines",
    )
    parser.add_argument("--generate-clips", action="store_true", help="Cut video clips")
    parser.add_argument("--concatenate", action="store_true", help="Join video clips")

    args = parser.parse_args()

    if args.transcribe:
        transcribe(args.input, args.hf_token, args.diarize)
    if args.extract_marked:
        extract_marked()
    if args.generate_clips:
        generate_clips(args.input)
    if args.concatenate:
        concatenate_clips()

    if not (
        args.transcribe or args.extract_marked or args.generate_clips or args.concatenate
    ):
        parser.print_help()


if __name__ == "__main__":
    main()

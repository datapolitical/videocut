#!/usr/bin/env python3
"""
align_mlx_mac.py  (v5 – works with new WhisperX CLI)

Zero-flag run:
    python align_mlx_mac.py
Produces:
    aligned.json
    aligned-dtw-transcript-mlx.txt
"""

import argparse, json, os, re, shutil, subprocess, sys, tempfile, uuid
from pathlib import Path

# default filenames -----------------------------------------------------------
DEF_VIDEO      = Path("input.mp4")
DEF_TRANSCRIPT = Path("dtw-transcript-mlx.txt")
DEF_JSON_OUT   = Path("aligned.json")

# deps -----------------------------------------------------------------------
FFMPEG  = shutil.which("ffmpeg")   or sys.exit("ffmpeg missing – brew install ffmpeg")
_       = shutil.which("whisperx") or sys.exit("whisperx missing – pip install 'whisperx[metal]'")

TIME_RX = re.compile(r"\[([\d.]+)\s*[–-]\s*([\d.]+)\]")
TMP_WAV = f"tmp_{uuid.uuid4().hex}.wav"

# helpers --------------------------------------------------------------------
def extract_wav(src: Path, dst: Path) -> None:
    print(f"• Extracting WAV from {src}")
    subprocess.run([FFMPEG, "-y", "-i", str(src), "-ac", "1", "-ar", "16000", str(dst)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def whisperx_align(wav: Path, transcript: Path, out_json: Path) -> None:
    print("• Running WhisperX align (Metal GPU)…")
    env = os.environ.copy()
    env["PYTORCH_METAL_ALLOW_PARTIAL_SHARED_MEMORY"] = "1"

    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            sys.executable, "-m", "whisperx", "align",
            str(wav), str(transcript),
            "--device", "mps",
            "--batch_size", "16",
            "--output_dir", tmp,
            "--output_format", "json"
        ]
        subprocess.run(cmd, check=True, env=env)
        out_json_path = next(Path(tmp).glob("*.json"))
        out_json_path.replace(out_json)
        print(f"  → aligned JSON saved to {out_json}")

def rewrite_tsv(orig_tsv: Path, aligned_json: Path) -> None:
    segs = json.load(aligned_json.open())["segments"]
    new_times = [(round(s["start"], 3), round(s["end"], 3)) for s in segs]

    out_tsv = orig_tsv.with_name(f"aligned-{orig_tsv.name}")
    with orig_tsv.open() as fin, out_tsv.open("w") as fout:
        for idx, line in enumerate(fin):
            if (m := TIME_RX.search(line)):
                s_new, e_new = new_times[idx]
                line = TIME_RX.sub(f"[{s_new:.3f} – {e_new:.3f}]", line, 1)
            fout.write(line)
    print(f"✓ Wrote {out_tsv}")

# main -----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video",      type=Path, default=DEF_VIDEO)
    ap.add_argument("--transcript", type=Path, default=DEF_TRANSCRIPT)
    ap.add_argument("--json_out",   type=Path, default=DEF_JSON_OUT)
    args = ap.parse_args()

    if not args.video.exists():      sys.exit(f"{args.video} not found")
    if not args.transcript.exists(): sys.exit(f"{args.transcript} not found")

    try:
        extract_wav(args.video, TMP_WAV)
        whisperx_align(Path(TMP_WAV), args.transcript, args.json_out)
    finally:
        Path(TMP_WAV).unlink(missing_ok=True)

    rewrite_tsv(args.transcript, args.json_out)
    print("✓ Done.")

if __name__ == "__main__":
    main()

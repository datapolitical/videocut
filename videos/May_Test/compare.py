#!/usr/bin/env python3
"""
clip_align_test_stubs.py
────────────────────────
Cuts six fresh paired clips *and* embeds, for each clip/transcript
pair, just the **opening and closing phrases** so you can quickly
eye-check the boundaries without dumping the entire text.

Run next to:
  • input.mp4                — full meeting video
  • dtw-transcript.txt       — “whisperx” transcript
  • dtw-transcript-mlx.txt   — “mlx” transcript

Creates 12 MP4s:
  S1_whisperx.mp4 … L2_mlx.mp4
and prints the stub texts to the console.
"""

import subprocess, textwrap

VIDEO_FILE = "input.mp4"   # full recording

# ────────────────────────────────────────────────────────────
# CLIP TIME WINDOWS  (seconds from start of VIDEO_FILE)
# ────────────────────────────────────────────────────────────
segments = {
    # SMALL (gap < 0.5 s)
    "S1": {"whisperx": (1973.196, 1990.874), "mlx": (1972.740, 1990.662)},
    "S2": {"whisperx": (3255.472, 3293.084), "mlx": (3255.920, 3294.660)},

    # MEDIUM (0.5–2 s)
    "M1": {"whisperx": (5543.555, 5691.510), "mlx": (5541.555, 5690.658)},
    "M2": {"whisperx": (5385.586, 5517.402), "mlx": (5383.770, 5517.625)},

    # LARGE (> 2 s)
    "L1": {"whisperx": (2202.064, 2238.046), "mlx": (2198.065, 2238.188)},
    "L2": {"whisperx": (4686.129, 4750.232), "mlx": (4682.696, 4751.010)},
}

# ────────────────────────────────────────────────────────────
# START / END SNIPPETS  (first ≈15 words … last ≈15 words)
# ────────────────────────────────────────────────────────────
stubs = {
    "S1": {
        "whisperx": {
            "start": "Karen Benker: Mr. Chair, if I could continue. Then how would you—something",
            "end":   "that are made. So however that is calculated, hopefully that is taken into consideration."
        },
        "mlx": {
            "start": "Karen Benker: Mr. Chair, if I could continue. Then how would you—something",
            "end":   "that are made. So however that is calculated, hopefully that is taken into consideration."
        },
    },
    "S2": {
        "whisperx": {
            "start": "Peggy Catlin: And you brought up a good point. I just know that when we",
            "end":   "talk about additional frequencies. Has that been discussed or called out in the current scope?"
        },
        "mlx": {
            "start": "Peggy Catlin: And you brought up a good point. I just know that when we",
            "end":   "talk about additional frequencies. Has that been discussed or called out in the current scope?"
        },
    },
    "M1": {
        "whisperx": {
            "start": "Tina Jaquez: I've been trying to meet with as many of our Board Directors",
            "end":   "thank you for indulging me while I lay out the gap-analysis road map …"
        },
        "mlx": {
            "start": "Tina Jaquez: I've been trying to meet with as many of our Board Directors",
            "end":   "thank you for indulging me while I lay out the gap-analysis road map …"
        },
    },
    "M2": {
        "whisperx": {
            "start": "Claire Levy: I appreciate that; I think it's really well founded given",
            "end":   "negotiations first, so again thank you for doing the hard work on the funding-needs perspective."
        },
        "mlx": {
            "start": "Claire Levy: I appreciate that; I think it's really well founded given",
            "end":   "negotiations first, so again thank you for doing the hard work on the funding-needs perspective."
        },
    },
    "L1": {
        "whisperx": {
            "start": "Julien Bouquet: Or something. So good to see you, Diane—Ms. Barrett. You",
            "end":   "I'm just kidding! But seriously, thank you."
        },
        "mlx": {
            "start": "Julien Bouquet: Or something. So good to see you, Diane—Ms. Barrett. You",
            "end":   "I'm just kidding! But seriously, thank you."
        },
    },
    "L2": {
        "whisperx": {
            "start": "Peggy Catlin: Thank you. Excuse me. Thank you. So I have a couple",
            "end":   "weekend service and bicycle capacity if that's okay …"
        },
        "mlx": {
            "start": "Peggy Catlin: Thank you. Excuse me. Thank you. So I have a couple",
            "end":   "weekend service and bicycle capacity if that's okay …"
        },
    },
}

# ────────────────────────────────────────────────────────────
def trim(start: float, end: float, outfile: str) -> None:
    subprocess.run(
        [
            "ffmpeg", "-loglevel", "error", "-y",
            "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
            "-i", VIDEO_FILE, "-c", "copy", outfile
        ],
        check=True
    )

def main() -> None:
    # export clips
    for label, versions in segments.items():
        for typ, (start, end) in versions.items():
            fname = f"{label}_{typ}.mp4"
            print(f"→ {fname:20} {start:8.2f}–{end:8.2f}s")
            trim(start, end, fname)

    # print stub texts
    print("\n=== START / END OF EACH CLIP ===")
    for label in ["S1", "S2", "M1", "M2", "L1", "L2"]:
        print(f"\n--- {label} ---")
        for typ in ["whisperx", "mlx"]:
            s = stubs[label][typ]["start"]
            e = stubs[label][typ]["end"]
            print(f"[{typ}]")
            print("  start:", textwrap.shorten(s, 120))
            print("  end:  ", textwrap.shorten(e, 120))
            print()

if __name__ == "__main__":
    main()

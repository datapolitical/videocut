#!/usr/bin/env python3
"""Step 6: concatenate clips into a final video."""
import argparse
from clip_utils import concatenate_clips


def main() -> None:
    p = argparse.ArgumentParser(description="Concatenate clips into final video")
    p.add_argument("--clips_dir", default="clips", help="Directory with clip files")
    p.add_argument("--out", default="final_video.mp4", help="Output video file")
    args = p.parse_args()
    concatenate_clips(args.clips_dir, args.out)


if __name__ == "__main__":
    main()

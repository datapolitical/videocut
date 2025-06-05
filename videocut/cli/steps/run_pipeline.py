#!/usr/bin/env python3
"""Orchestrate the video-cutting pipeline.

Steps:
1. :mod:`videocut.cli.steps.transcribe_step` – run WhisperX.
2. :mod:`videocut.cli.steps.json_to_tsv_step` or :mod:`videocut.cli.steps.json_to_editable_step` – prepare TSV or
   JSON for manual editing.
3. :mod:`videocut.cli.steps.identify_clips_step`, :mod:`videocut.cli.steps.identify_clips_json_step` or
   :mod:`videocut.cli.steps.extract_marked_step` – create ``segments_to_keep.json``.
4. :mod:`videocut.cli.steps.auto_mark_nicholson_step` – optional auto-detection via diarization.
5. :mod:`videocut.cli.steps.generate_clips_step` – cut clips.
6. :mod:`videocut.cli.steps.concatenate_clips_step` – join clips together.
"""
import argparse
import os
from videocut.core.transcribe import transcribe
from videocut.core.clip_utils import (
    json_to_tsv,
    json_to_editable,
    identify_clips,
    identify_clips_json,
    extract_marked,
    auto_mark_nicholson,
    generate_clips,
    concatenate_clips,
)


def main() -> None:
    p = argparse.ArgumentParser("run_pipeline")
    p.add_argument("--input", default="input.mp4", help="Input video file")
    p.add_argument("--hf_token", default=os.getenv("HF_TOKEN"), help="Hugging Face token")
    p.add_argument("--diarize", action="store_true", help="Use speaker diarization")
    p.add_argument("--tsv", default="input.tsv", help="TSV file for identify_clips")
    p.add_argument("--json", default=None, help="WhisperX JSON for conversion steps")
    p.add_argument("--segments", default="segments_to_keep.json", help="JSON segments file")
    p.add_argument("--clips_dir", default="clips", help="Output clips directory")
    p.add_argument("--final", default="final_video.mp4", help="Final video filename")

    p.add_argument("--transcribe", action="store_true", help="Run WhisperX transcription")
    p.add_argument("--json_to_tsv", action="store_true", help="Convert JSON → TSV")
    p.add_argument(
        "--json_to_editable",
        action="store_true",
        help="Create editable JSON with Timestamp/content/pre/post fields",
    )
    p.add_argument("--identify_clips", action="store_true", help="Parse TSV to JSON")
    p.add_argument("--identify_clips_json", action="store_true", help="Parse editable JSON to segments")
    p.add_argument("--extract_marked", action="store_true", help="Parse markup guide to JSON")
    p.add_argument("--auto_mark_nicholson", action="store_true", help="Auto-mark Nicholson segments")
    p.add_argument("--generate_clips", action="store_true", help="Cut clips from segments JSON")
    p.add_argument("--concatenate", action="store_true", help="Join clips into final video")
    p.add_argument("--all", action="store_true", help="Run all steps in order")

    args = p.parse_args()

    def run(cond, func, *f_args):
        if cond:
            func(*f_args)

    run(args.transcribe or args.all, transcribe, args.input, args.hf_token, args.diarize)
    run(args.json_to_tsv or args.all, json_to_tsv, args.json or f"{os.path.splitext(args.input)[0]}.json", args.tsv)
    run(args.json_to_editable or args.all, json_to_editable, args.json or f"{os.path.splitext(args.input)[0]}.json", "segments_edit.json")
    run(args.identify_clips or args.all, identify_clips, args.tsv, args.segments)
    run(args.identify_clips_json or args.all, identify_clips_json, "segments_edit.json", args.segments)
    run(args.extract_marked or args.all, extract_marked, "markup_guide.txt", args.segments)
    run(args.auto_mark_nicholson, auto_mark_nicholson, f"{os.path.splitext(args.input)[0]}.json", args.segments)
    run(args.generate_clips or args.all, generate_clips, args.input, args.segments, args.clips_dir)
    run(args.concatenate or args.all, concatenate_clips, args.clips_dir, args.final)

    if not any([
        args.transcribe,
        args.json_to_tsv,
        args.json_to_editable,
        args.identify_clips,
        args.identify_clips_json,
        args.extract_marked,
        args.auto_mark_nicholson,
        args.generate_clips,
        args.concatenate,
        args.all,
    ]):
        p.print_help()


if __name__ == "__main__":
    main()

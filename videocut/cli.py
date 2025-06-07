"""Typer-based command line interface for VideoCut."""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import typer
from .core import (
    transcription,
    segmentation,
    video_editing,
    nicholson,
    annotation,
    clip_transcripts,
    speaker_mapping,
)

app = typer.Typer(help="VideoCut pipeline")


@app.command()
def transcribe(
    video: str = typer.Argument("input.mp4", help="Video file to transcribe"),
    diarize: bool = typer.Option(False, help="Perform speaker diarization"),
    hf_token: Optional[str] = typer.Option(None, envvar="HF_TOKEN", help="Hugging Face token for diarization"),
    speaker_db: Optional[str] = typer.Option(None, help="Speaker embedding database JSON"),
):
    """Run WhisperX transcription."""
    transcription.transcribe(video, hf_token, diarize, speaker_db)


@app.command()
def json_to_editable(
    json_file: str,
    out: str = "segments_edit.json",
    markup: str = "markup_guide.txt",
):
    segmentation.json_to_editable(json_file, out, markup)


@app.command()
def json_to_tsv(json_file: str, out: str = "input.tsv"):
    segmentation.json_to_tsv(json_file, out)


@app.command()
def identify_clips(tsv: str = "input.tsv", out: str = "segments_to_keep.json"):
    segmentation.identify_clips(tsv, out)


@app.command()
def identify_clips_json(edit_json: str = "segments_edit.json", out: str = "segments_to_keep.json"):
    segmentation.identify_clips_json(edit_json, out)


@app.command()
def extract_marked(markup: str = "markup_guide.txt", out: str = "segments_to_keep.json"):
    segmentation.extract_marked(markup, out)

@app.command()
def annotate_markup(markup_file: str = "markup_guide.txt", seg_json: str = "segments_to_keep.json", out_file: str = "markup_with_markers.txt"):
    annotation.annotate_segments(markup_file, seg_json, out_file)

@app.command()
def clip_transcripts_cmd(markup_file: str = "markup_guide.txt", seg_json: str = "segments_to_keep.json", out_file: str = "clip_transcripts.txt"):
    clip_transcripts.clip_transcripts(markup_file, seg_json, out_file)


@app.command()
def build_speaker_db(samples: str, out: str = "speaker_db.json"):
    """Process WAV samples into a speaker embedding database."""
    speaker_mapping.build_speaker_db(samples, out)


@app.command()
def map_speakers(video: str, json_file: str, db: str = "speaker_db.json", out: Optional[str] = None):
    """Apply speaker name mapping to a diarized JSON file."""
    speaker_mapping.apply_speaker_map(video, json_file, db, out)

@app.command()
def auto_mark_nicholson(json_file: str, out: str = "segments_to_keep.json"):
    nicholson.auto_mark_nicholson(json_file, out)


@app.command()
def generate_clips(
    video: str = typer.Argument("input.mp4", help="Source video"),
    segs: str = typer.Option("segments_to_keep.json", help="Segments JSON"),
    out_dir: str = typer.Option("clips", help="Output directory for clips"),
):
    video_editing.generate_clips(video, segs, out_dir)


@app.command()
def concatenate(clips_dir: str = "clips", out: str = "final_video.mp4"):
    video_editing.concatenate_clips(clips_dir, out)


@app.command()
def pipeline(
    video: str = typer.Argument("input.mp4", help="Input video file"),
    diarize: bool = typer.Option(False, help="Perform speaker diarization"),
    hf_token: Optional[str] = typer.Option(None, envvar="HF_TOKEN", help="Hugging Face token for diarization"),
    auto_nicholson: bool = typer.Option(True, help="Automatically mark Secretary Nicholson"),
    speaker_db: Optional[str] = typer.Option(None, help="Speaker embedding database JSON"),
):
    """Run the full pipeline, auto-marking Nicholson by default."""
    transcription.transcribe(video, hf_token, diarize, speaker_db)
    json_file = f"{Path(video).stem}.json"
    if auto_nicholson:
        nicholson.auto_mark_nicholson(json_file, "segments_to_keep.json")
    else:
        segmentation.json_to_editable(json_file, "segments_edit.json", "markup_guide.txt")
        segmentation.identify_clips_json("segments_edit.json", "segments_to_keep.json")
    video_editing.generate_clips(video, "segments_to_keep.json", "clips")
    video_editing.concatenate_clips("clips", "final_video.mp4")


def main() -> None:
    """Run the Typer application."""
    app()


if __name__ == "__main__":
    main()

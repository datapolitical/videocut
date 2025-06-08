"""Typer-based command line interface for VideoCut."""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import json
import typer
from .core import (
    transcription,
    segmentation,
    video_editing,
    nicholson,
    annotation,
    clip_transcripts,
    speaker_mapping,
    chair,
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
def identify_speakers(
    diarized_json: str,
    mapping: str,
    out: str = "speaker_map.json",
):
    """Map named people to diarized speaker IDs based on key phrases."""
    phrase_map = json.loads(Path(mapping).read_text())
    ids = nicholson.map_speaker_by_phrases(diarized_json, phrase_map)
    Path(out).write_text(json.dumps(ids, indent=2))
    print(f"✅  speaker map → {out}")


@app.command()
def identify_recognized(
    diarized_json: str,
    out: str = "recognized_map.json",
):
    """Automatically map recognized names to speaker IDs."""
    ids = nicholson.map_recognized_auto(diarized_json)
    chair_id = chair.identify_chair(diarized_json)
    Path(out).write_text(json.dumps(ids, indent=2))
    print(f"🔍  chair is {chair_id}")
    print(f"✅  recognized map → {out}")


@app.command()
def identify_chair(
    diarized_json: str,
    out: str = "roll_call_map.json",
):
    """Detect the chair and parse roll call responses."""
    chair_id = chair.identify_chair(diarized_json)
    votes = chair.parse_roll_call(diarized_json)
    Path(out).write_text(json.dumps(votes, indent=2))
    print(f"🔍  chair is {chair_id}")
    print(f"✅  roll call map → {out}")


@app.command()
def apply_speaker_labels(
    diarized_json: str,
    map_json: str,
    out: str = "labeled.json",
):
    """Write a copy of diarized_json with speaker names in a 'label' field."""
    mapping = json.loads(Path(map_json).read_text())
    nicholson.add_speaker_labels(diarized_json, mapping, out)


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
    # ``speaker_db`` may be Typer's ``OptionInfo`` sentinel when this command
    # is invoked programmatically (e.g. by tests). Only pass it through when it
    # is an actual string path so patched versions of :func:`transcription.transcribe`
    # that accept the original 3 arguments continue to work.
    if isinstance(speaker_db, str) and speaker_db:
        transcription.transcribe(video, hf_token, diarize, speaker_db)
    else:
        transcription.transcribe(video, hf_token, diarize)
    json_file = f"{Path(video).stem}.json"

    if diarize:
        try:
            ids = nicholson.map_recognized_auto(json_file)
            Path("recognized_map.json").write_text(json.dumps(ids, indent=2))
            print("✅  recognized map → recognized_map.json")
        except Exception as exc:
            print(f"⚠️  automatic recognition failed: {exc}")

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

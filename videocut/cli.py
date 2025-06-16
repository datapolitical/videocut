"""Typer-based command line interface for VideoCut."""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import json
import typer
from videocut.core.align import align_pdf_to_asr
from videocut.core.dtw_align import align_pdf_to_srt
from videocut.core.convert import matched_to_txt
from videocut.core.label_fix import labelify
from .core import (
    transcription,
    segmentation,
    video_editing,
    nicholson,
    annotation,
    clip_transcripts,
    srt_markers,
    alignment,
    align,
    speaker_mapping,
    chair,
    pdf_utils,
)

app = typer.Typer(help="VideoCut pipeline")


@app.command()
def transcribe(
    video: str = typer.Argument("input.mp4", help="Video file to transcribe"),
    diarize: bool = typer.Option(False, help="Perform speaker diarization"),
    hf_token: Optional[str] = typer.Option(
        None, envvar="HF_TOKEN", help="Hugging Face token for diarization"
    ),
    speaker_db: Optional[str] = typer.Option(
        None, help="Speaker embedding database JSON"
    ),
    progress: bool = typer.Option(True, help="Show WhisperX progress output"),
    pdf: Optional[str] = typer.Option(None, help="Official PDF transcript"),
):
    """Run WhisperX transcription."""
    transcription.transcribe(video, hf_token, diarize, speaker_db, progress, pdf)


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
def json_to_markup(json_file: str, out: str = "markup_guide.txt"):
    """Generate ``markup_guide.txt`` from a diarized JSON file."""
    segmentation.json_to_markup(json_file, out)


@app.command()
def identify_clips(tsv: str = "input.tsv", out: str = "segments_to_keep.json"):
    segmentation.identify_clips(tsv, out)


@app.command()
def identify_clips_json(
    edit_json: str = "segments_edit.json", out: str = "segments_to_keep.json"
):
    segmentation.identify_clips_json(edit_json, out)


@app.command()
def extract_marked(
    markup: str = "markup_guide.txt", out: str = "segments_to_keep.json"
):
    segmentation.extract_marked(markup, out)


@app.command()
def annotate_markup(
    markup_file: str = "markup_guide.txt",
    seg_file: str = "segments.txt",
    out_file: str = "markup_with_markers.txt",
    srt_file: Optional[str] = None,
):
    annotation.annotate_segments(markup_file, seg_file, out_file, srt_file)


@app.command()
def clip_transcripts_cmd(
    markup_file: str = "markup_guide.txt",
    seg_file: str = "segments.txt",
    out_file: str = "clip_transcripts.txt",
    srt_file: Optional[str] = None,
):
    clip_transcripts.clip_transcripts(markup_file, seg_file, out_file, srt_file)


@app.command("pdf-transcript")
def apply_pdf_transcript(
    json_file: str,
    pdf_path: str,
    out_json: Optional[str] = None,
):
    """Apply an official PDF transcript to a diarized JSON."""
    pdf_utils.apply_pdf_transcript_json(json_file, pdf_path, out_json)


@app.command("json-to-transcript")
def json_to_transcript(
    json_file: str, pdf: Optional[str] = None, out: str = "transcript.txt"
):
    """Generate ``transcript.txt`` using timestamps from ``json_file``.

    When ``pdf`` is supplied the transcript lines from the PDF are
    merged into the JSON prior to generating ``transcript.txt`` so that
    the output reflects the official wording.
    """
    tmp_json = json_file
    if pdf:
        tmp_json = str(Path(json_file).with_suffix(".pdf.json"))
        pdf_utils.apply_pdf_transcript_json(json_file, pdf, tmp_json)
    pdf_utils.write_timestamped_transcript(
        pdf or json_file,
        json_file,
        out,
        json_path=tmp_json,
    )
    if pdf:
        Path(tmp_json).unlink(missing_ok=True)


@app.command("check-transcript")
def check_transcript(json_file: str, min_wps: float = 0.5, max_wps: float = 5.0):
    """Report segments with abnormal words-per-second timing."""
    bad = pdf_utils.find_timing_anomalies(json_file, min_wps, max_wps)
    if not bad:
        print("✅  transcript timings look reasonable")
    else:
        for seg in bad:
            preview = seg["text"][:60].replace("\n", " ")
            print(
                f"{seg['index']:04d} {seg['start']:.2f}-{seg['end']:.2f} "
                f"{seg['wps']:.2f} wps: {preview}"
            )
        print(f"⚠️  {len(bad)} suspicious segment(s)")


@app.command("pdf-extract")
def pdf_extract(
    pdf_file: str, txt_out: Optional[str] = None, json_out: Optional[str] = None
):
    """Extract transcript from PDF to text and JSON."""
    pdf_utils.export_pdf_transcript(pdf_file, txt_out, json_out)


@app.command("pdf-match")
def pdf_match(pdf_file: str, json_file: str, out: str = "matched.json"):
    """Match PDF transcript lines to a diarized JSON."""
    pdf_utils.match_pdf_json(pdf_file, json_file, out)


# ---------------------------------------------------------------------
# Align PDF → ASR
@app.command("match")
def match_cli(
    pdf_json: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="pdf_transcript.json produced from the PDF",
    ),
    asr_json: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="WhisperX meeting JSON with word-level timestamps",
    ),
    out: Path = typer.Option(
        Path("matched.json"),
        "--out",
        "-o",
        help="Destination file for the aligned transcript",
    ),
    window: int = typer.Option(
        120,
        help="Sliding window size in words",
    ),
    step: int = typer.Option(
        30,
        help="Hop length between windows",
    ),
    ratio: float = typer.Option(
        0.15,
        help="Minimum SequenceMatcher ratio to accept a match",
    ),
) -> None:
    """
    Align PDF utterances (no timestamps) to ASR word stream and write *matched.json*.
    """
    matched = align_pdf_to_asr(
        pdf_json,
        asr_json,
        window=window,
        step=step,
        ratio_thresh=ratio,
    )
    out.write_text(json.dumps(matched, indent=2))
    nulls = sum(1 for m in matched if m["start"] is None)
    typer.echo(f"✅ wrote {out} · {nulls} unmatched line(s)")


# ---------------------------------------------------------------------
# Advanced DTW alignment
@app.command("dtw-align")
def dtw_align(
    pdf_txt: Path = typer.Argument(..., exists=True, readable=True),
    srt_path: Path = typer.Argument(..., exists=True, readable=True),
    json_out: Path = typer.Option("matched_dtw.json", "--json-out", "-j"),
    txt_out: Path = typer.Option("dtw-transcript.txt", "--txt-out", "-t"),
    band: int = typer.Option(100, help="DTW half-band width (tokens)"),
):
    """Advanced banded-DTW word-level alignment of PDF to SRT.

    Writes *matched_dtw.json* and a speaker-labeled *dtw-transcript.txt*.
    """
    aligned = align_pdf_to_srt(pdf_txt, srt_path, band=band)
    json_out.write_text(json.dumps(aligned, indent=2))
    labelify(json_out, txt_out)
    typer.echo(
        f"✅ wrote {json_out} and {txt_out} with {len(aligned)} sentences"
    )


# ---------------------------------------------------------------------
# matched.json → transcript.txt
@app.command("to-txt")
def to_txt_cli(
    matched_json: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="matched.json produced by `videocut match`",
    ),
    out: Path = typer.Option(
        Path("transcript.txt"),
        "--out",
        "-o",
        help="Destination tab-indented TXT for `videocut segment`",
    ),
) -> None:
    """
    Convert *matched.json* to the tab-indented transcript.txt format.
    """
    matched_to_txt(matched_json, out)
    typer.echo(f"✅ wrote {out}")


@app.command("make-labeled")
def make_labeled(
    matched_json: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="matched_DTW.json or any match output",
    ),
    out_file: Path = typer.Option(
        "labeled_transcript.txt",
        "--out",
        "-o",
        help="Destination TXT file",
    ),
    default: str = typer.Option(
        "Unknown",
        help="Fallback speaker when no prior label is available",
    ),
) -> None:
    """
    Ensure every line has an explicit speaker tag.

    Output line format:
        Speaker<TAB>[start-end]<TAB>utterance
    """
    labelify(matched_json, out_file, default_speaker=default)
    typer.echo(f"✅ wrote {out_file}")


@app.command("align")
def align_cmd(
    video: str,
    transcript: str,
    out_json: str = "aligned.json",
):
    """Align ``transcript`` with ``video``.

    When a PDF file is supplied it is converted to ``transcript.txt`` before
    alignment.
    """
    alignment.align_with_transcript(video, transcript, out_json)


@app.command()
def annotate_srt(
    srt_file: str,
    seg_json: str = "segments_to_keep.json",
    name_map: str = "recognized_map.json",
    out_file: Optional[str] = None,
):
    """Write ``out_file`` with =START/=END markers and mapped labels.

    If ``out_file`` is ``None`` it will be derived from ``srt_file`` by
    appending ``_processed`` before the extension. For example,
    ``meeting.srt`` becomes ``meeting_processed.srt``.
    """
    if out_file is None:
        path = Path(srt_file)
        out_file = f"{path.stem}_processed{path.suffix}"
    srt_markers.annotate_srt(srt_file, seg_json, name_map, out_file)


@app.command()
def srt_to_segments(srt_file: str, out: str = "segments_from_srt.json"):
    """Extract segment list from an annotated SRT file."""
    segs = srt_markers.segments_from_srt(srt_file)
    Path(out).write_text(json.dumps(segs, indent=2))
    print(f"✅  {len(segs)} segment(s) → {out}")


@app.command()
def clips_from_srt(
    video: str = typer.Argument("input.mp4", help="Source video"),
    srt_file: str = typer.Argument("processed.srt", help="SRT with markers"),
    out_dir: str = typer.Option("clips", help="Output directory for clips"),
):
    """Generate clips directly from an annotated SRT."""
    segs = srt_markers.segments_from_srt(srt_file)
    video_editing.generate_clips_from_segments(video, segs, out_dir)


@app.command()
def build_speaker_db(samples: str, out: str = "speaker_db.json"):
    """Process WAV samples into a speaker embedding database."""
    speaker_mapping.build_speaker_db(samples, out)


@app.command()
def map_speakers(
    video: str, json_file: str, db: str = "speaker_db.json", out: Optional[str] = None
):
    """Apply speaker name mapping to a diarized JSON file."""
    speaker_mapping.apply_speaker_map(video, json_file, db, out)


@app.command("identify-segments")
def identify_segments_cmd(
    source: str = typer.Argument(..., help="Diarized JSON or transcript file"),
    recognized: str = "recognized_map.json",
    board_file: str = "board_members.txt",
    out_txt: str = "segments.txt",
):
    """Detect Nicholson segments from a diarized JSON or transcript file."""
    tmp_json = Path(out_txt).with_suffix(".json")
    if source.endswith(".json"):
        nicholson.identify_segments(source, recognized, str(tmp_json), board_file)
    else:
        nicholson.segment_nicholson_from_transcript(source, str(tmp_json), board_file)
    segmentation.segments_json_to_txt(source, str(tmp_json), out_txt)
    tmp_json.unlink(missing_ok=True)


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
def apply_name_map(
    seg_json: str = "segments_to_keep.json",
    map_json: str = "recognized_map.json",
    out: Optional[str] = None,
):
    """Replace SPEAKER IDs in segments JSON with recognized names."""
    nicholson.apply_name_map(seg_json, map_json, out)


@app.command()
def prune_segments_cmd(
    seg_json: str = "segments_to_keep.json",
    out: Optional[str] = None,
):
    """Remove trivial segments from the JSON list."""
    nicholson.prune_segments(seg_json, out)


@app.command("segment")
def segment(
    json_file: Path = typer.Argument(
        "videos/May_Board_Meeting.json",
        help="Diarized JSON transcript or tab-indented transcript.txt",
    ),
    speaker: str = "Chris Nicholson",
    out: Path = Path("segments.txt"),
):
    """Write Nicholson segments from *json_file* to ``segments.txt``.

    If ``json_file`` ends with ``.txt`` it is treated as a raw transcript and
    processed with :mod:`segmenter`.
    """
    json_file = Path(json_file)
    out = Path(out)

    if json_file.suffix == ".txt":
        from . import segmenter

        typer.echo("Using new segmenter 2.0 code")
        rows = segmenter.load_rows(str(json_file))
        seg_lines = segmenter.build_segments(rows)
        out.write_text("\n".join(seg_lines) + "\n")
        typer.echo(f"✅ Created {out}")
        return

    tmp_json = json_file.with_name("segments_auto.json")
    nicholson.segment_nicholson(str(json_file), str(tmp_json))
    segmentation.segments_json_to_txt(str(json_file), str(tmp_json), str(out))
    tmp_json.unlink(missing_ok=True)
    typer.echo(f"✅ Created {out}")


@app.command()
def recognized_directors(
    recognized: str = "recognized_map.json",
    board_file: str = "board_members.txt",
    out: str = "recognized_directors.txt",
):
    """Generate recognized_directors.txt from recognition results."""
    nicholson.generate_recognized_directors(recognized, board_file, out)


@app.command()
def generate_clips(
    video: str = typer.Argument("input.mp4", help="Source video"),
    segs: str = typer.Argument("segments.txt", help="Segments file (txt or json)"),
    out_dir: str = typer.Option("clips", help="Output directory for clips"),
    srt_file: Optional[str] = typer.Option(None, help="SRT file for segments.txt"),
):
    video_editing.generate_clips(video, segs, out_dir, srt_file)


@app.command()
def concatenate(clips_dir: str = "clips", out: str = "final_video.mp4"):
    video_editing.concatenate_clips(clips_dir, out)


@app.command()
def pipeline(
    video: str = typer.Argument("input.mp4", help="Input video file"),
    hf_token: str = typer.Option(
        ..., envvar="HF_TOKEN", help="Hugging Face token for diarization"
    ),
    speaker_db: Optional[str] = typer.Option(
        None, help="Speaker embedding database JSON"
    ),
    pdf: Optional[str] = typer.Option(None, help="Official PDF transcript"),
):
    """Run the full board‑meeting pipeline."""
    use_pdf = isinstance(pdf, str) and pdf
    if use_pdf:
        if isinstance(speaker_db, str) and speaker_db:
            transcription.transcribe(video, hf_token, True, speaker_db, True, pdf)
        else:
            transcription.transcribe(video, hf_token, True, pdf_path=pdf)
    else:
        if isinstance(speaker_db, str) and speaker_db:
            transcription.transcribe(video, hf_token, True, speaker_db)
        else:
            transcription.transcribe(video, hf_token, True)

    json_file = f"{Path(video).stem}.json"
    ids = nicholson.map_recognized_auto(json_file)
    Path("recognized_map.json").write_text(json.dumps(ids, indent=2))
    roll = chair.parse_roll_call(json_file)
    Path("roll_call_map.json").write_text(json.dumps(roll, indent=2))

    # Apply recognized names to the JSON and regenerate markup guide
    nicholson.apply_name_map_json(json_file, "recognized_map.json", json_file)
    segmentation.json_to_markup(json_file, "markup_guide.txt")

    tmp_json = "segments.json"
    nicholson.identify_segments(
        json_file,
        "recognized_map.json",
        tmp_json,
        "board_members.txt",
    )
    segmentation.segments_json_to_txt(tmp_json, "segments.txt")
    Path(tmp_json).unlink(missing_ok=True)
    video_editing.generate_clips(video, "segments.txt", "clips")
    video_editing.concatenate_clips("clips", "final_video.mp4")
    annotation.annotate_segments(
        "markup_guide.txt", "segments.txt", "markup_with_markers.txt"
    )
    clip_transcripts.clip_transcripts(
        "markup_guide.txt", "segments.txt", "clip_transcripts.txt"
    )


def main() -> None:
    """Run the Typer application."""
    app()


if __name__ == "__main__":
    main()

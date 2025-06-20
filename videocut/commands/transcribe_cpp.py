import subprocess
from pathlib import Path
import click
from whispercpp_to_transcript import convert_whispercpp_to_transcript


@click.command()
@click.argument('input_file')
@click.option('--model', default='models/ggml-base.en.bin', help='Path to whisper.cpp model')
@click.option('--output', default='transcript.txt', help='Output transcript path')
def transcribe_cpp(input_file, model, output):
    """Transcribe using whisper.cpp."""
    input_path = Path(input_file)
    wav_path = input_path.with_suffix('.wav')

    if not wav_path.exists():
        subprocess.run(['ffmpeg', '-y', '-i', str(input_path), str(wav_path)], check=True)

    subprocess.run([
        './main',
        '-m', model,
        '-f', str(wav_path),
        '-otxt'
    ], check=True)

    convert_whispercpp_to_transcript('output.txt', output)


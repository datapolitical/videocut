import sys
import mlx_whisper

def format_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

if len(sys.argv) < 2:
    print("Usage: python transcribe_mlx.py <audio_or_video_file>")
    sys.exit(1)

input_file = sys.argv[1]
print(f"[INFO] Transcribing: {input_file}")

result = mlx_whisper.transcribe(
    input_file,
    path_or_hf_repo="mlx-community/whisper-tiny",  # Or base/small
    word_timestamps=True
)

# Write full text
with open("markup_guide.txt", "w") as f:
    f.write(result["text"].strip())
print("[INFO] Wrote full transcript to markup_guide.txt")

# Segment-level SRT
with open("transcript.srt", "w") as srt:
    for idx, segment in enumerate(result["segments"], 1):
        start = format_timestamp(segment["start"])
        end = format_timestamp(segment["end"])
        text = segment["text"].strip()
        srt.write(f"{idx}\n{start} --> {end}\n{text}\n\n")
print("[INFO] Wrote segment-aligned SRT to transcript.srt")

# Word-level SRT
with open("transcript.words.srt", "w") as word_srt:
    idx = 1
    for segment in result["segments"]:
        for word in segment.get("words", []):
            start = format_timestamp(word["start"])
            end = format_timestamp(word["end"])
            text = word["word"].strip()
            word_srt.write(f"{idx}\n{start} --> {end}\n{text}\n\n")
            idx += 1
print("[INFO] Wrote word-by-word SRT to transcript.words.srt")

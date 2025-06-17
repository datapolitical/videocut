import os
import re
from datetime import timedelta
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials


def parse_segments_for_chapters(segments_file: str, fade_duration: float = 0.5):
    with open(segments_file, 'r') as f:
        lines = [line.rstrip() for line in f.readlines()]

    chapters = []
    current_time = 0.0
    in_segment = False
    pattern = re.compile(r"\[(\d+):(\d+)-(\d+):(\d+)\]\s+(.+?):\s+(.*)")

    for line in lines:
        if line.strip() == "=START=":
            in_segment = True
        elif line.strip() == "=END=":
            in_segment = False
        elif in_segment and line.startswith("\t") and pattern.search(line):
            sm, ss, em, es, speaker, text = pattern.search(line).groups()
            seg_duration = (int(em)*60 + int(es)) - (int(sm)*60 + int(ss))
            timestamp = seconds_to_timestamp(current_time)
            title = f"{speaker.strip()}: {text.strip()}"
            chapters.append((timestamp, title))
            current_time += seg_duration + fade_duration

    return chapters

def seconds_to_timestamp(seconds: float) -> str:
    td = timedelta(seconds=int(seconds))
    minutes = td.seconds // 60
    seconds = td.seconds % 60
    return f"{minutes:02d}:{seconds:02d}"

def build_description_from_segments(segments_file: str, fade_duration: float = 0.5):
    chapters = parse_segments_for_chapters(segments_file, fade_duration)
    return "\n".join(f"{ts} {title}" for ts, title in chapters)

def upload_video_to_youtube(video_path, title, tags, category_id, privacy_status, creds_file, description):
    creds = Credentials.from_authorized_user_file(creds_file)
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": privacy_status
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

    print("[⏳] Uploading video...")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    print(f"[✅] Video uploaded: https://www.youtube.com/watch?v={response['id']}")

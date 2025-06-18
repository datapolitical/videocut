#!/bin/bash

# Check for yt-dlp
if ! command -v yt-dlp &> /dev/null; then
  echo "Error: yt-dlp is not installed. Install it with 'brew install yt-dlp' or visit https://github.com/yt-dlp/yt-dlp"
  exit 1
fi

# Check if URL is passed
if [ -z "$1" ]; then
  echo "Usage: $0 <youtube-url>"
  exit 1
fi

URL="$1"

# Run yt-dlp with your preferred format
yt-dlp -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]" --merge-output-format mp4 -o "%(title)s.%(ext)s" "$URL"

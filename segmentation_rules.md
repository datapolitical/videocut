# Segmentation Rules

These rules describe how `segmenter.py` builds `segments.txt` for the Nicholson highlight reel.

1. **Gluing** – If two Nicholson clips are less than 30 seconds apart, they are merged into a single segment. Material between them is included in that segment.
2. **Transcript Input** – Input lines may be flush-left or tab indented. Each non-marker output line is indented with a single tab.
3. **Markers** – `=START=` and `=END=` appear flush-left and wrap kept segments.
4. **Chair Hand‑off** – When the chair (`Julien Bouquet`) speaks a line beginning with "Director " or containing "thank you, secretary", the current segment ends just before that line.
5. **Opening a Segment** – A segment starts only when `Chris Nicholson` speaks a substantive line containing **at least ten words**. Short acknowledgements such as "Thank you, Chair" do not open a segment.
6. **Closing the File** – If a segment remains open at the end of the transcript, an `=END=` marker is appended.

These rules match the logic implemented in `videocut/segmenter.py`.

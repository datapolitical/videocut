# Segmentation Rules

These rules describe how `segmenter.py` builds `segments.txt` for the Nicholson highlight reel.

1. **Gluing** – If two Nicholson clips are less than 30 seconds apart **or separated by four or fewer transcript lines**, they are merged into a single segment. Material between them is included in that segment.
2. **Transcript Input** – Input lines may be flush-left or tab indented. Each non-marker output line is indented with a single tab.
3. **Markers** – `=START=` and `=END=` appear flush-left and wrap kept segments.
4. **Chair Hand‑off** – When the chair (`Julien Bouquet`) mentions a director by name or by official title (for example, "Treasurer Benker") and that director speaks next, the current segment ends just before the chair's line. Recognition of staff or non‑directors does not end the segment.
5. **Opening a Segment** – A segment starts only when `Chris Nicholson` speaks a substantive line containing **at least ten words**. Short acknowledgements such as "Thank you, Chair" do not open a segment.
6. **Closing the File** – If a segment remains open at the end of the transcript, an `=END=` marker is appended.

These rules match the logic implemented in `videocut/segmenter.py`.

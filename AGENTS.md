Only run tests/test_segments_format.py and test_segments_txt_roundtrip tests. Do not run any other tests.

A recognition statement is when the chair speaks, mentions someone's name and then that person speaks. Like so:
[3272.70 - 3276.89] Julien Bouquet: Director Guzman.
[3277.33 - 3288.90] Michael Guzman: I got one quick. 

A nicholson segment should always start with director nicholson speaking, so no lines before that are necessary. 
a nicholson segment ends when another director is recognized. 

two segments within 30 seconds of one another are acutally part of the same segment and all material between them is part of that segment. 

As of commit f212b7: 
- the transcribe code is frozen, don't change that. 
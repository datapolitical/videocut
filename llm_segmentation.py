import re, json
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

MODEL = 'google/flan-t5-small'
tokenizer = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL)

lines = Path('videos/example/markup_guide.txt').read_text().splitlines()
segments = []
cur_start = None
last_end = None

for line in lines:
    m = re.match(r"\[(\d+\.\d+)-(\d+\.\d+)\]\s*(.*)", line)
    if not m:
        continue
    start = float(m.group(1))
    end = float(m.group(2))
    text = m.group(3)
    prompt = (
        "Secretary Nicholson is designated as SPEAKER_00. "
        "Does this line show a statement from SPEAKER_00? "
        "Answer yes or no only: " + text
    )
    inputs = tokenizer(prompt, return_tensors='pt')
    outputs = model.generate(**inputs, max_length=5)
    ans = tokenizer.decode(outputs[0], skip_special_tokens=True).strip().lower()
    is_nicholson = ans.startswith('yes')
    if is_nicholson:
        if cur_start is None:
            cur_start = start
        last_end = end
    else:
        if cur_start is not None:
            segments.append({'start': cur_start, 'end': last_end})
            cur_start = None
            last_end = None

if cur_start is not None:
    segments.append({'start': cur_start, 'end': last_end})

Path('segments_llm.json').write_text(json.dumps(segments, indent=2))
print(f"LLM segments -> segments_llm.json")

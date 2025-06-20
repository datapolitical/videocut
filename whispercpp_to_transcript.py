import re

def convert_whispercpp_to_transcript(input_path, output_path):
    with open(input_path, 'r') as f:
        lines = f.readlines()

    with open(output_path, 'w') as out:
        for line in lines:
            match = re.match(r"\[(\d\d:\d\d:\d\d\.\d\d\d) --> (\d\d:\d\d:\d\d\.\d\d\d)\] (.*)", line)
            if match:
                start, end, text = match.groups()
                out.write(f"[{start}-{end}] UNKNOWN: {text.strip()}\n")


import pathlib, subprocess, filecmp, shutil

SEG = pathlib.Path('segments.txt')
SRC = pathlib.Path('segmenter.py')


def test_tab_indentation():
    lines = SEG.read_text().splitlines()
    for ln in lines:
        if ln in ('=START=', '=END=') or not ln.strip():
            continue
        assert ln.startswith('\t'), f"Missing tab: {ln}"


def test_roundtrip(tmp_path, monkeypatch):
    orig = tmp_path / 'orig.txt'
    shutil.copy(SEG, orig)
    subprocess.run(['python', SRC], check=True)
    assert filecmp.cmp(SEG, orig), 'Round-trip changed segments.txt'

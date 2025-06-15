import pathlib
import subprocess
import filecmp
import shutil
import sys

SEG = pathlib.Path('segments.txt')


def test_tab_indentation():
    lines = SEG.read_text().splitlines()
    for ln in lines:
        if ln in ('=START=', '=END=') or not ln.strip():
            continue
        assert ln.startswith('\t'), f"Missing tab: {ln}"


def test_roundtrip(tmp_path, monkeypatch):
    orig = tmp_path / 'orig.txt'
    shutil.copy(SEG, orig)
    subprocess.run([sys.executable, '-m', 'videocut.segmenter'], check=True)
    assert filecmp.cmp(SEG, orig), 'Round-trip changed segments.txt'

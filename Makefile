.PHONY: install install-dev reinstall clean

# Full install: base + transcribe + dev
install:
	. .venv/bin/activate && pip install -e ".[transcribe,dev]"

# Dev-only install (no whisperx/torch)
install-dev:

	python3 -m venv .venv
	. .venv/bin/activate
	python -m pip install -U pip setuptools wheel
	pip install -e ".[dev]"

# Reinstall into venv (clean + install)
reinstall:
	. .venv/bin/activate && pip uninstall -y videocut && pip install -e ".[transcribe,dev]"

# Clean compiled files and artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf *.egg-info

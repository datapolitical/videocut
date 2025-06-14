.PHONY: install install-dev clean

# Full install: base + transcribe + dev
install:
	pip install -e ".[transcribe,dev]"

# Dev-only install (no whisperx/torch)
install-dev:
	pip install -e ".[dev]"

# Clean compiled files and artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf *.egg-info

.PHONY: install install-dev reinstall clean

# Install all deps (including optional groups like 'transcribe' and 'dev')
install:
	poetry install --with transcribe,dev

# Install only dev dependencies
install-dev:
	poetry install --only dev

# Reinstall from scratch
reinstall:
	poetry install --with transcribe,dev --no-root

# Clean Python build artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf *.egg-info

.PHONY: install install-dev reinstall clean debug-env

# Install all deps (including optional groups like 'transcribe' and 'dev')
install:
	@echo "==> Running full install with 'transcribe' and 'dev' extras"
	poetry install --extras "transcribe dev"

# Install only dev dependencies
install-dev:
	@echo "==> Running dev-only install (should NOT include whisperx)"
	poetry install --extras "dev"
	@echo "==> Installed packages:"
	poetry show

# Reinstall from scratch
reinstall:
	@echo "==> Reinstalling from scratch with 'transcribe' and 'dev' extras"
	rm -rf .venv poetry.lock
	poetry lock
	poetry install --extras "transcribe dev" --no-root

# Clean Python build artifacts
clean:
	@echo "==> Cleaning Python build artifacts"
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf *.egg-info

# Debug which package pulled in whisperx
debug-env:
	@echo "==> Checking if whisperx is installed and why"
	poetry show whisperx || echo "whisperx is not installed"
	poetry show --why --tree whisperx || echo "No dependency path for whisperx"


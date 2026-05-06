.PHONY: install test lint format clean

install:
	uv venv .venv
	uv pip install -r requirements-dev.txt

test:
	python3 -m pytest

lint:
	pre-commit run --all-files

format:
	black .
	ruff check . --fix

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

.PHONY: install test lint format clean

install:
	poetry install

test:
	poetry run pytest tests/ -v

lint:
	poetry run ruff check voyageur/ tests/

format:
	poetry run ruff format voyageur/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +

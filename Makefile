.PHONY: install dev start test lint fmt check

install:
	poetry install

dev:
	poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

start:
	poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000

test:
	poetry run pytest

lint:
	poetry run ruff check .

fmt:
	poetry run ruff format .

check: lint test

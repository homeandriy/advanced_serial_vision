.DEFAULT_GOAL := help
UV ?= uv

.PHONY: help install run check test lint format typecheck verify lock

help:
	@echo "make install  Sync locked runtime and development dependencies"
	@echo "make run      Start Serial Vision"
	@echo "make check    Check Python syntax"
	@echo "make test     Run tests"
	@echo "make lint     Check Ruff rules and formatting"
	@echo "make format   Apply Ruff fixes and formatting"
	@echo "make typecheck Check types in the core modules"
	@echo "make verify   Check lock, syntax, lint, types and tests"
	@echo "make lock     Resolve dependencies after pyproject changes"

install:
	$(UV) sync --locked

run:
	$(UV) run --locked serial-vision

check:
	$(UV) run --locked python -m compileall -q application

test:
	$(UV) run --locked python -m unittest discover -s application/tests

lint:
	$(UV) run --locked ruff check .
	$(UV) run --locked ruff format --check .

format:
	$(UV) run --locked ruff format .
	$(UV) run --locked ruff check --fix .
	$(UV) run --locked ruff format .

typecheck:
	$(UV) run --locked mypy

lock:
	$(UV) lock

verify:
	$(UV) lock --check
	$(MAKE) check lint typecheck test

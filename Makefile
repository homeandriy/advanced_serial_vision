.DEFAULT_GOAL := help
UV ?= uv

.PHONY: help install run check test lint format typecheck verify lock updater-translations check-translations check-text install-hooks build-server

help:
	@echo "make install  Sync locked runtime and development dependencies"
	@echo "make run      Start Serial Vision"
	@echo "make check    Check Python syntax"
	@echo "make test     Run tests"
	@echo "make lint     Check Ruff rules and formatting"
	@echo "make format   Apply Ruff fixes and formatting"
	@echo "make typecheck Check types throughout the application"
	@echo "make verify   Check lock, syntax, lint, types and tests"
	@echo "make lock     Resolve dependencies after pyproject changes"
	@echo "make updater-translations Generate the standalone updater catalog"
	@echo "make check-text Check UTF-8 without BOM and LF in tracked text files"
	@echo "make install-hooks Enable the pre-commit text check"
	@echo "make build-server Build the headless warehouse server executable"

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

updater-translations:
	$(UV) run --locked python scripts/generate_updater_translations.py

check-translations:
	$(UV) run --locked python scripts/generate_updater_translations.py --check

verify:
	$(UV) lock --check
	$(MAKE) check-text check lint check-translations typecheck test

check-text:
	$(UV) run --locked python scripts/check_text_files.py

install-hooks:
	git config core.hooksPath .githooks

build-server:
	$(UV) run --locked --extra build pyinstaller --noconfirm tools/warehouse-server.spec

.DEFAULT_GOAL := help
PYTHON ?= python

.PHONY: help install run check test

help:
	@echo "make install  Install Python dependencies"
	@echo "make run      Start Serial Vision"
	@echo "make check    Check Python syntax"
	@echo "make test     Run tests"

install:
	$(PYTHON) -m pip install -e .

run:
	$(PYTHON) -m serial_vision.main

check:
	$(PYTHON) -m compileall -q application

test:
	$(PYTHON) -m unittest discover -s application/tests


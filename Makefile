PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: lint test run-paper install venv

venv:
	python3 -m venv .venv

install: venv
	$(PIP) install -e ".[dev]"

lint:
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m ruff format --check src tests

test:
	$(PYTHON) -m pytest -q

run-paper:
	$(PYTHON) -m grokbot run --mode paper --once

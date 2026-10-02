PY ?= .venv/bin/python
STRATEGY ?=

.PHONY: venv test lint gate gate-all nightly clean

venv:
	python3.11 -m venv .venv || python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -e ".[dev]"

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .

gate:
	@test -n "$(STRATEGY)" || (echo "usage: make gate STRATEGY=<name>" && exit 2)
	$(PY) -m eval.gate $(STRATEGY)

gate-all:
	$(PY) -m eval.gate --all

nightly:
	$(PY) -m ops.nightly postmortem && $(PY) -m ops.nightly summary

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

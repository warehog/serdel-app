.PHONY: venv install run fmt lint

venv:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -U pip

install: venv
	. .venv/bin/activate && pip install -e .

run:
	. .venv/bin/activate && deck --help

fmt:
	. .venv/bin/activate && ruff format src
	. .venv/bin/activate && ruff check --fix src || true
PYTHON ?= .venv/bin/python

.PHONY: install install-dev test build check verify

install:
	$(PYTHON) -m pip install -c constraints.txt -r requirements.txt

install-dev:
	$(PYTHON) -m pip install -r requirements-dev.txt

test:
	$(PYTHON) -m pytest -q

build:
	$(PYTHON) build_samples.py

check:
	$(PYTHON) manage.py check --render

verify: test build

PYTHON ?= .venv/bin/python
NPM ?= npm

.PHONY: install install-dev test build check verify

install:
	$(PYTHON) -m pip install -c constraints.txt -r requirements.txt
	$(NPM) ci --omit=dev --ignore-scripts --no-audit --no-fund

install-dev:
	$(PYTHON) -m pip install -r requirements-dev.txt
	$(NPM) ci --ignore-scripts --no-audit --no-fund

test:
	$(PYTHON) -m pytest -q

build:
	$(PYTHON) build_samples.py

check:
	$(PYTHON) manage.py check --render

verify: test build

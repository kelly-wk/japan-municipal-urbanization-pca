BOOTSTRAP_PYTHON ?= python3
VENV_PYTHON := .venv/bin/python
PYTHON ?= $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),python3)

.PHONY: setup fetch prepare analyze test reproduce

setup:
	$(BOOTSTRAP_PYTHON) -m venv .venv
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.lock -e .

fetch:
	$(PYTHON) scripts/download_sources.py --output data/raw

prepare:
	PYTHONPATH=src $(PYTHON) -m urban_pca.cli prepare \
		--source-2024 data/raw/2024 \
		--source-2026 data/raw/2026 \
		--output data/processed/municipal_indicators.csv

analyze:
	PYTHONPATH=src $(PYTHON) -m urban_pca.cli analyze \
		--input data/processed/municipal_indicators.csv \
		--output results \
		--seed 20260929 \
		--bootstrap 1000 \
		--validation-bootstrap 2000

test:
	PYTHONPATH=src $(PYTHON) -m pytest

reproduce: analyze test

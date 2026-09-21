# ============================================================
# Makefile — Process Intelligence + Agentic Automation Engine
# Uses conda environment located at ./venv
# ============================================================

CONDA_ENV := $(CURDIR)/venv
PYTHON    := conda run --no-capture-output --prefix $(CONDA_ENV) python
PIP       := conda run --no-capture-output --prefix $(CONDA_ENV) pip

.PHONY: env setup test lint run clean

## Create the conda environment (Python 3.11) in ./venv
env:
	conda create --prefix $(CONDA_ENV) python=3.11 -y

## Install all project dependencies into the conda env
setup: env
	$(PIP) install -e ".[dev]"

## Run all tests (no live API calls — uses deterministic provider)
test:
	conda run --no-capture-output --prefix $(CONDA_ENV) pytest tests/ -v --tb=short

## Run linter
lint:
	conda run --no-capture-output --prefix $(CONDA_ENV) ruff check src/ tests/

## Launch the Streamlit app
run:
	conda run --no-capture-output --prefix $(CONDA_ENV) streamlit run app.py

## Remove generated artefacts (not the conda env)
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache

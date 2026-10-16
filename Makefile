# ============================================================
# Makefile — Process Intelligence + Agentic Automation Engine
# Uses a conda environment located at ./venv
# ============================================================

CONDA_ENV := $(CURDIR)/venv
RUN       := conda run --no-capture-output --prefix $(CONDA_ENV)

.PHONY: help env setup test lint format run data clean

## Show available targets
help:
	@echo "setup   create ./venv and install the package + dev tools"
	@echo "run     launch the Streamlit app"
	@echo "test    run the test suite"
	@echo "lint    ruff check"
	@echo "format  black"
	@echo "data    regenerate data/event_logs.csv"
	@echo "clean   remove caches"

## Create the conda environment (Python 3.11) in ./venv
env:
	conda create --prefix $(CONDA_ENV) python=3.11 -y

## Install the package and dev tools into the conda env
setup: env
	$(RUN) pip install -e ".[dev]"

## Run the test suite (deterministic provider — no live API calls)
test:
	$(RUN) pytest

## Lint with ruff
lint:
	$(RUN) ruff check src tests app.py

## Auto-format with black
format:
	$(RUN) black src tests app.py

## Launch the Streamlit app
run:
	$(RUN) streamlit run app.py

## Regenerate data/event_logs.csv
data:
	$(RUN) python -m process_agent.generators.log_generator

## Remove generated artefacts (not the conda env)
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache

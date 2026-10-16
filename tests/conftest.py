"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Allow running the suite without `pip install -e .`
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from process_agent.generators.log_generator import generate_event_log  # noqa: E402


@pytest.fixture(scope="session")
def demo_log() -> pd.DataFrame:
    """A small, reproducible synthetic event log shared across tests."""
    return generate_event_log(num_cases=300, seed=7)

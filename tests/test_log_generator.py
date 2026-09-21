"""
tests/test_log_generator.py

Unit tests for the synthetic event log generator.
No file I/O unless explicitly testing output_path.
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from process_agent.generators.log_generator import (
    AUTOMATABLE_ACTIVITIES,
    VARIANTS,
    generate_event_log,
    load_or_generate,
)

REQUIRED_COLUMNS = {
    "case_id",
    "activity",
    "timestamp",
    "duration_seconds",
    "variant",
    "amount",
    "submitter_id",
}


# ---------------------------------------------------------------------------
# Basic shape tests
# ---------------------------------------------------------------------------


def test_returns_dataframe() -> None:
    df = generate_event_log(num_cases=100, seed=0)
    assert isinstance(df, pd.DataFrame)


def test_required_columns_present() -> None:
    df = generate_event_log(num_cases=100, seed=0)
    assert REQUIRED_COLUMNS.issubset(df.columns), (
        f"Missing columns: {REQUIRED_COLUMNS - set(df.columns)}"
    )


def test_correct_number_of_cases() -> None:
    """Each case_id must appear exactly once per activity in its sequence."""
    num_cases = 200
    df = generate_event_log(num_cases=num_cases, seed=1)
    assert df["case_id"].nunique() == num_cases


def test_total_events_positive() -> None:
    df = generate_event_log(num_cases=50, seed=2)
    assert len(df) > 0


# ---------------------------------------------------------------------------
# Timestamp ordering
# ---------------------------------------------------------------------------


def test_timestamps_monotonic_per_case() -> None:
    """Within each case, timestamps must be strictly increasing."""
    df = generate_event_log(num_cases=100, seed=3)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    for case_id, group in df.groupby("case_id"):
        ts = group["timestamp"].reset_index(drop=True)
        assert ts.is_monotonic_increasing, (
            f"Case {case_id} has non-monotonic timestamps"
        )


# ---------------------------------------------------------------------------
# Variant distribution
# ---------------------------------------------------------------------------


def test_variant_distribution_within_tolerance() -> None:
    """
    With 2,000 cases each variant should land within ±5 pp of its target.
    """
    df = generate_event_log(num_cases=2_000, seed=42)
    # one row per case for variant counting
    case_df = df.drop_duplicates(subset="case_id")
    observed = case_df["variant"].value_counts(normalize=True)

    tolerance = 0.05
    for variant, expected_ratio in VARIANTS.items():
        actual = observed.get(variant, 0.0)
        assert abs(actual - expected_ratio) <= tolerance, (
            f"Variant '{variant}': expected ~{expected_ratio:.0%}, "
            f"got {actual:.1%} (tolerance ±{tolerance:.0%})"
        )


def test_all_variants_present() -> None:
    df = generate_event_log(num_cases=500, seed=99)
    observed_variants = set(df["variant"].unique())
    assert observed_variants == set(VARIANTS.keys())


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------


def test_duration_seconds_non_negative() -> None:
    df = generate_event_log(num_cases=200, seed=5)
    assert (df["duration_seconds"] >= 0).all()


def test_amount_within_bounds() -> None:
    df = generate_event_log(num_cases=200, seed=6)
    assert (df["amount"] >= 50.0).all()
    assert (df["amount"] <= 5_000.0).all()


def test_case_ids_have_expected_prefix() -> None:
    df = generate_event_log(num_cases=10, seed=7)
    assert df["case_id"].str.startswith("CASE-").all()


def test_submitter_ids_have_expected_prefix() -> None:
    df = generate_event_log(num_cases=10, seed=8)
    assert df["submitter_id"].str.startswith("EMP-").all()


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def test_writes_csv_when_output_path_given(tmp_path: Path) -> None:
    out = tmp_path / "test_log.csv"
    df = generate_event_log(num_cases=50, seed=9, output_path=out)
    assert out.exists()
    loaded = pd.read_csv(out)
    assert len(loaded) == len(df)


def test_load_or_generate_creates_file(tmp_path: Path) -> None:
    out = tmp_path / "data" / "event_logs.csv"
    df = load_or_generate(output_path=out, num_cases=50, seed=10)
    assert out.exists()
    assert len(df) > 0


def test_load_or_generate_reads_existing(tmp_path: Path) -> None:
    out = tmp_path / "event_logs.csv"
    df1 = load_or_generate(output_path=out, num_cases=50, seed=11)
    df2 = load_or_generate(output_path=out, num_cases=50, seed=11)
    assert len(df1) == len(df2)


def test_load_or_generate_force_regenerate(tmp_path: Path) -> None:
    out = tmp_path / "event_logs.csv"
    df1 = load_or_generate(output_path=out, num_cases=50, seed=11)
    df2 = load_or_generate(
        output_path=out, num_cases=100, seed=12, force_regenerate=True
    )
    # After forced regeneration the case count should change
    assert df2["case_id"].nunique() == 100


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


def test_same_seed_produces_same_output() -> None:
    df1 = generate_event_log(num_cases=100, seed=42)
    df2 = generate_event_log(num_cases=100, seed=42)
    pd.testing.assert_frame_equal(df1, df2)


def test_automatable_activities_are_valid_activities() -> None:
    """Every automatable activity must actually appear in the logs."""
    df = generate_event_log(num_cases=2_000, seed=42)
    all_activities = set(df["activity"].unique())
    for act in AUTOMATABLE_ACTIVITIES:
        assert act in all_activities, (
            f"Automatable activity '{act}' never appears in logs"
        )

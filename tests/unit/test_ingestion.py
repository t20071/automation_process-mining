"""Unit tests for event-log ingestion (column mapping, validation, cleaning)."""

from __future__ import annotations

import pandas as pd

from process_agent.ingestion import map_columns, normalise_event_log


def test_aliases_are_mapped_to_canonical_names() -> None:
    raw = pd.DataFrame({"Case ID": ["A"], "Task": ["submit"], "Start Time": ["2024-01-01"],
                        "Elapsed": [10]})
    df, mapping = map_columns(raw)
    assert {"case_id", "activity", "timestamp", "duration_seconds"} <= set(df.columns)
    assert mapping["Case ID"] == "case_id"


def test_missing_required_columns_are_reported() -> None:
    result = normalise_event_log(pd.DataFrame({"foo": [1], "bar": [2]}))
    assert not result.ok
    assert "Missing required columns" in result.errors[0]


def test_durations_are_derived_when_absent() -> None:
    raw = pd.DataFrame({
        "case_id": ["A", "A", "A"],
        "activity": ["submit", "approve", "pay"],
        "timestamp": ["2024-01-01 00:00", "2024-01-01 01:00", "2024-01-01 03:00"],
    })
    result = normalise_event_log(raw)
    assert result.ok
    assert result.df["duration_seconds"].tolist() == [3600.0, 7200.0, 0.0]
    assert any("derived" in n for n in result.notes)


def test_optional_columns_get_defaults_and_bad_rows_are_dropped() -> None:
    raw = pd.DataFrame({
        "case_id": ["A", "A"], "activity": ["submit", "pay"],
        "timestamp": ["2024-01-01", "not-a-date"], "duration_seconds": [5, 5],
    })
    result = normalise_event_log(raw)
    assert result.ok
    assert len(result.df) == 1
    assert {"variant", "amount", "submitter_id"} <= set(result.df.columns)


def test_unparseable_timestamps_fail_cleanly() -> None:
    raw = pd.DataFrame({"case_id": ["A"], "activity": ["x"], "timestamp": ["nope"]})
    assert not normalise_event_log(raw).ok

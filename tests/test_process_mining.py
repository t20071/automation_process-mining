"""
tests/test_process_mining.py

Unit tests for the process mining module.
Uses small in-memory fixture DataFrames — no file I/O.
"""

from __future__ import annotations

import pandas as pd
import pytest

from process_agent.mining.process_mining import (
    ActivityStats,
    DFGEdge,
    ProcessMap,
    _build_dfg,
    _compute_activity_stats,
    _count_variants,
    _flag_automatable,
    _flag_bottlenecks,
    _validate_df,
    cycle_time_summary,
    discover_process_map,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_simple_log() -> pd.DataFrame:
    """
    Minimal happy-path log: 3 cases, each with submit → approval → paid.
    """
    rows = []
    base = pd.Timestamp("2024-01-01", tz="UTC")
    for case_num in range(1, 4):
        rows += [
            {
                "case_id": f"CASE-{case_num}",
                "activity": "submit",
                "timestamp": base,
                "duration_seconds": 300.0,
                "variant": "happy_path",
                "amount": 100.0,
                "submitter_id": "EMP-001",
            },
            {
                "case_id": f"CASE-{case_num}",
                "activity": "approval",
                "timestamp": base + pd.Timedelta(hours=1),
                "duration_seconds": 3_600.0,
                "variant": "happy_path",
                "amount": 100.0,
                "submitter_id": "EMP-001",
            },
            {
                "case_id": f"CASE-{case_num}",
                "activity": "paid",
                "timestamp": base + pd.Timedelta(hours=2),
                "duration_seconds": 600.0,
                "variant": "happy_path",
                "amount": 100.0,
                "submitter_id": "EMP-001",
            },
        ]
    return pd.DataFrame(rows)


def _make_full_log() -> pd.DataFrame:
    """
    Use the real log generator for integration-style tests.
    Small scale (200 cases) for speed.
    """
    from process_agent.generators.log_generator import generate_event_log

    return generate_event_log(num_cases=200, seed=0)


# ---------------------------------------------------------------------------
# _validate_df
# ---------------------------------------------------------------------------


def test_validate_raises_on_missing_columns() -> None:
    df = pd.DataFrame({"case_id": [1], "activity": ["a"]})
    with pytest.raises(ValueError, match="missing required columns"):
        _validate_df(df)


def test_validate_raises_on_empty_df() -> None:
    df = pd.DataFrame(
        columns=["case_id", "activity", "timestamp", "duration_seconds"]
    )
    with pytest.raises(ValueError, match="empty"):
        _validate_df(df)


def test_validate_passes_on_valid_df() -> None:
    df = _make_simple_log()
    _validate_df(df)  # must not raise


# ---------------------------------------------------------------------------
# _compute_activity_stats
# ---------------------------------------------------------------------------


def test_activity_stats_keys_match_activities() -> None:
    df = _make_simple_log()
    stats = _compute_activity_stats(df)
    assert set(stats.keys()) == {"submit", "approval", "paid"}


def test_activity_stats_mean_correct() -> None:
    df = _make_simple_log()
    stats = _compute_activity_stats(df)
    # All submit events have duration_seconds = 300
    assert stats["submit"].mean_seconds == pytest.approx(300.0)


def test_activity_stats_count_correct() -> None:
    df = _make_simple_log()
    stats = _compute_activity_stats(df)
    assert stats["submit"].count == 3
    assert stats["approval"].count == 3


# ---------------------------------------------------------------------------
# _flag_bottlenecks
# ---------------------------------------------------------------------------


def test_bottleneck_flagging_marks_top_n() -> None:
    df = _make_full_log()
    stats = _compute_activity_stats(df)
    bottlenecks = _flag_bottlenecks(stats, top_n=3)
    assert len(bottlenecks) == 3
    for act in bottlenecks:
        assert stats[act].is_bottleneck is True


def test_non_bottleneck_activities_not_flagged() -> None:
    df = _make_full_log()
    stats = _compute_activity_stats(df)
    bottlenecks = _flag_bottlenecks(stats, top_n=3)
    non_bottlenecks = set(stats.keys()) - set(bottlenecks)
    for act in non_bottlenecks:
        assert stats[act].is_bottleneck is False


# ---------------------------------------------------------------------------
# _flag_automatable
# ---------------------------------------------------------------------------


def test_automatable_activities_have_low_cv() -> None:
    df = _make_full_log()
    stats = _compute_activity_stats(df)
    automatable = _flag_automatable(stats, cv_threshold=0.30, min_count=5)
    for act in automatable:
        s = stats[act]
        cv = s.std_seconds / s.mean_seconds if s.mean_seconds else float("inf")
        assert cv <= 0.30, f"{act} has CV={cv:.2f} but was flagged automatable"


# ---------------------------------------------------------------------------
# _build_dfg
# ---------------------------------------------------------------------------


def test_dfg_has_correct_edges() -> None:
    df = _make_simple_log()
    G, edges = _build_dfg(df)
    edge_pairs = {(e.source, e.target) for e in edges}
    assert ("submit", "approval") in edge_pairs
    assert ("approval", "paid") in edge_pairs


def test_dfg_edge_frequency_correct() -> None:
    df = _make_simple_log()
    _, edges = _build_dfg(df)
    edge_map = {(e.source, e.target): e.frequency for e in edges}
    # 3 cases × 1 submit→approval transition
    assert edge_map[("submit", "approval")] == 3


def test_dfg_graph_is_directed() -> None:
    import networkx as nx

    df = _make_simple_log()
    G, _ = _build_dfg(df)
    assert isinstance(G, nx.DiGraph)


# ---------------------------------------------------------------------------
# discover_process_map (full pipeline)
# ---------------------------------------------------------------------------


def test_discover_returns_process_map() -> None:
    df = _make_full_log()
    pm = discover_process_map(df)
    assert isinstance(pm, ProcessMap)


def test_discover_bottlenecks_count() -> None:
    df = _make_full_log()
    pm = discover_process_map(df)
    assert len(pm.bottlenecks) == 3


def test_discover_variant_counts_all_present() -> None:
    df = _make_full_log()
    pm = discover_process_map(df)
    expected = {"happy_path", "escalation", "rejection_loop", "exception"}
    assert expected.issubset(pm.variant_counts.keys())


def test_discover_graph_has_nodes() -> None:
    df = _make_full_log()
    pm = discover_process_map(df)
    assert pm.graph.number_of_nodes() > 0


# ---------------------------------------------------------------------------
# cycle_time_summary
# ---------------------------------------------------------------------------


def test_cycle_time_summary_returns_dataframe() -> None:
    df = _make_full_log()
    pm = discover_process_map(df)
    summary = cycle_time_summary(pm)
    assert isinstance(summary, pd.DataFrame)


def test_cycle_time_summary_sorted_by_std() -> None:
    df = _make_full_log()
    pm = discover_process_map(df)
    summary = cycle_time_summary(pm)
    stds = summary["std_seconds"].tolist()
    assert stds == sorted(stds, reverse=True)


def test_cycle_time_summary_has_expected_columns() -> None:
    df = _make_full_log()
    pm = discover_process_map(df)
    summary = cycle_time_summary(pm)
    expected_cols = {
        "activity", "mean_seconds", "std_seconds",
        "p95_seconds", "count", "is_bottleneck", "is_automatable",
    }
    assert expected_cols.issubset(summary.columns)

"""Unit tests for case-level analytics, health score, insights and ROI."""

from __future__ import annotations

import pandas as pd
import pytest

from process_agent.mining import analytics
from process_agent.mining.process_mining import discover_process_map


@pytest.fixture(scope="module")
def mined(demo_log: pd.DataFrame):
    return discover_process_map(demo_log), analytics.case_table(demo_log)


def test_case_table_has_one_row_per_case(demo_log: pd.DataFrame, mined) -> None:
    _, cases = mined
    assert len(cases) == demo_log["case_id"].nunique()
    assert (cases["throughput_seconds"] >= 0).all()


def test_rejection_loop_cases_are_flagged_as_rework(mined) -> None:
    _, cases = mined
    assert cases[cases["variant"] == "rejection_loop"]["has_rework"].all()
    assert not cases[cases["variant"] == "happy_path"]["has_rework"].any()


def test_path_summary_shares_sum_to_one(mined) -> None:
    _, cases = mined
    paths = analytics.path_summary(cases, top_n=50)
    assert paths["share"].sum() == pytest.approx(1.0)


def test_health_score_is_bounded(mined) -> None:
    pm, cases = mined
    health = analytics.health_score(cases, pm)
    assert 0 <= health.score <= 100
    assert health.label in {"Healthy", "Fair", "At risk"}


def test_insights_are_generated(demo_log: pd.DataFrame, mined) -> None:
    pm, cases = mined
    insights = analytics.generate_insights(demo_log, cases, pm, ["submit", "paid"])
    assert insights
    assert all(i.tone in {"risk", "opportunity", "info"} for i in insights)


def test_roi_scales_with_adoption(demo_log: pd.DataFrame, mined) -> None:
    _, cases = mined
    full = analytics.estimate_roi(demo_log, cases, {"submit": 0.9}, adoption=1.0)
    half = analytics.estimate_roi(demo_log, cases, {"submit": 0.9}, adoption=0.5)
    assert half.hours_saved == pytest.approx(full.hours_saved / 2, rel=0.01)
    assert full.after_mean_days <= full.before_mean_days


def test_fmt_duration() -> None:
    assert analytics.fmt_duration(30) == "30s"
    assert analytics.fmt_duration(120) == "2m"
    assert analytics.fmt_duration(7_200) == "2.0h"
    assert analytics.fmt_duration(172_800) == "2.0d"

"""Unit tests for the process-map DOT builder."""

from __future__ import annotations

import pandas as pd

from process_agent.mining.process_mining import discover_process_map
from process_agent.ui.components.charts import build_dot


def test_dot_contains_every_activity_and_endpoints(demo_log: pd.DataFrame) -> None:
    pm = discover_process_map(demo_log)
    dot = build_dot(pm, {})
    assert dot.startswith("digraph")
    assert '"__start__"' in dot and '"__end__"' in dot
    for activity in pm.activity_stats:
        assert f'"{activity}"' in dot


def test_rare_transitions_can_be_hidden(demo_log: pd.DataFrame) -> None:
    pm = discover_process_map(demo_log)
    full = build_dot(pm, {}, min_share=0.0)
    trimmed = build_dot(pm, {}, min_share=0.9)
    assert trimmed.count("->") < full.count("->")

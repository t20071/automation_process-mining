"""
src/process_agent/ui/views/process_map.py

Process-map tab: interactive Directly-Follows Graph (rendered client-side
from DOT) plus per-activity cycle-time analysis.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from process_agent.ui.analysis import Analysis
from process_agent.ui.components import charts
from process_agent.ui.components.theme import STATUS, status_badge


def _activity_rows(a: Analysis) -> pd.DataFrame:
    status = a.status_by_activity
    return pd.DataFrame([{
        "activity": s.activity,
        "status_label": STATUS.get(status.get(s.activity, ""), {}).get("label", "Other"),
        "mean_hours": s.mean_seconds / 3_600,
        "p95_hours": s.p95_seconds / 3_600,
        "std_hours": s.std_seconds / 3_600,
        "cv": s.std_seconds / s.mean_seconds if s.mean_seconds else 0.0,
        "count": s.count,
    } for s in a.pm.activity_stats.values()])


def render_process_map_tab(a: Analysis) -> None:
    with st.container(horizontal=True, vertical_alignment="bottom"):
        metric = st.segmented_control(
            "Edge labels", ["frequency", "time"], default="frequency", key="map_metric",
            format_func={"frequency": "Case frequency", "time": "Mean wait"}.get,
            required=True)
        detail = st.slider("Hide rare transitions below", 0, 50, 0, 5, format="%d%%",
                           key="map_detail", width=260,
                           help="Relative to the busiest transition. Raise it to "
                                "simplify spaghetti-like processes.")
    st.markdown("  ".join(status_badge(s) for s in STATUS)
                + "  ·  edge thickness ∝ frequency · dashed = start/end")
    dot = charts.build_dot(a.pm, a.status_by_activity, metric or "frequency", detail / 100)
    with st.container(border=True):
        st.graphviz_chart(dot, width="stretch")
    st.download_button("Download map (DOT)", dot, "process_map.dot", "text/vnd.graphviz",
                       icon=":material/download:", type="tertiary")

    rows = _activity_rows(a)
    with st.container(border=True):
        st.markdown("**Where the time goes** — mean duration per activity, tick = P95")
        st.altair_chart(charts.activity_duration_chart(rows), width="stretch")
    st.dataframe(
        rows.sort_values("mean_hours", ascending=False)[
            ["activity", "status_label", "count", "mean_hours", "p95_hours", "std_hours", "cv"]],
        hide_index=True, width="stretch",
        column_config={
            "activity": "Activity", "status_label": "Status",
            "count": st.column_config.NumberColumn("Executions", format="localized"),
            "mean_hours": st.column_config.NumberColumn("Mean (h)", format="%.1f"),
            "p95_hours": st.column_config.NumberColumn("P95 (h)", format="%.1f"),
            "std_hours": st.column_config.NumberColumn("Std dev (h)", format="%.1f"),
            "cv": st.column_config.ProgressColumn("Variability (CV)", format="%.2f",
                                                  min_value=0, max_value=1),
        },
    )

"""
src/process_agent/ui/views/overview.py

Overview tab: KPI row, process health, key findings, weekly trends and the
most frequent process paths.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from process_agent.mining import analytics
from process_agent.ui.analysis import Analysis
from process_agent.ui.components import charts
from process_agent.ui.components.theme import eyebrow


def _kpis(a: Analysis, trend: pd.DataFrame, health: analytics.HealthScore) -> None:
    cases = a.cases
    auto = len(a.activities_with("automatable"))
    tone = {"Healthy": "green", "Fair": "orange", "At risk": "red"}[health.label]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Cases", f"{len(cases):,}", border=True, height="stretch",
              chart_data=trend["cases"].tolist()[-26:], chart_type="bar",
              help="Cases started per week")
    c2.metric("Median throughput", f"{cases['throughput_days'].median():.1f} d",
              border=True, height="stretch",
              chart_data=trend["median_days"].round(2).tolist()[-26:],
              help="End-to-end time from first to last event, per start week")
    c3.metric("Rework rate", f"{cases['has_rework'].mean():.0%}", border=True,
              height="stretch",
              help="Cases that repeat a step or are rejected and resubmitted")
    c4.metric("Automation-ready", f"{auto} / {len(a.advice)}", border=True,
              height="stretch", help="Activities the advisor classifies as automatable")
    c5.metric("Process health", f"{health.score}/100", health.label, border=True,
              height="stretch", delta_color=tone, delta_arrow="off",
              help="40% conformance to the dominant path + 30% rework-free cases "
                   "+ 30% duration predictability")


def _findings(insights: list[analytics.Insight]) -> None:
    tone_color = {"risk": "red", "opportunity": "blue", "info": "violet"}
    eyebrow("Key findings")
    for ins in insights:
        with st.container(border=True):
            st.markdown(f":{tone_color[ins.tone]}[:material/{ins.icon}:] **{ins.title}**")
            st.caption(ins.detail)


def _health_card(health: analytics.HealthScore) -> None:
    eyebrow("Health breakdown")
    with st.container(border=True):
        parts = [
            ("Conformance", health.conformance, "Cases on the most common path (40%)"),
            ("Rework-free", health.rework_free, "Cases with no loops (30%)"),
            ("Predictability", health.predictability, "1 − weighted duration CV (30%)"),
        ]
        for name, value, help_text in parts:
            st.progress(min(max(value, 0.0), 1.0), text=f"**{name}** · {value:.0%}")
            st.caption(help_text)


def render_overview_tab(df: pd.DataFrame, a: Analysis) -> None:
    trend = analytics.weekly_trend(a.cases)
    health = analytics.health_score(a.cases, a.pm)
    insights = analytics.generate_insights(df, a.cases, a.pm, a.activities_with("automatable"))
    _kpis(a, trend, health)

    left, right = st.columns([1.6, 1], gap="medium")
    with left:
        _findings(insights)
    with right:
        _health_card(health)

    c1, c2 = st.columns(2, gap="medium")
    with c1.container(border=True):
        st.markdown("**Cases started per week**")
        st.altair_chart(charts.weekly_volume_chart(trend), width="stretch")
    with c2.container(border=True):
        st.markdown("**Median throughput by start week**")
        st.altair_chart(charts.weekly_throughput_chart(trend), width="stretch")

    with st.container(border=True):
        st.markdown("**Process paths** — distinct activity sequences, most frequent first")
        paths = analytics.path_summary(a.cases)
        st.dataframe(
            paths[["path", "cases", "share", "median_days", "p90_days"]],
            hide_index=True, width="stretch",
            column_config={
                "path": st.column_config.TextColumn("Path", width="large"),
                "cases": st.column_config.NumberColumn("Cases", format="localized"),
                "share": st.column_config.ProgressColumn("Share", format="percent",
                                                         min_value=0, max_value=1),
                "median_days": st.column_config.NumberColumn("Median (days)", format="%.2f"),
                "p90_days": st.column_config.NumberColumn("P90 (days)", format="%.2f"),
            },
        )

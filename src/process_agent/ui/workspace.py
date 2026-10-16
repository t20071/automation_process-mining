"""
src/process_agent/ui/workspace.py

Workspace shown once an event log is loaded: sidebar (dataset, analysis
settings, agent status) and the six analysis tabs.  Presentation only —
every number comes from the mining / analytics / advisor modules.

Tabs
----
Overview       KPIs, health score, key findings, trends, top paths
Process map    interactive DFG + activity cycle-time analysis
Automation     per-activity advice: status, why, how, tools
Decision gate  scripted scenarios, sandbox, live agent, audit trail
Impact & ROI   adjustable assumptions -> annualised savings
Event log      data quality and raw events
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from process_agent.config import Settings
from process_agent.ui.analysis import analyse
from process_agent.ui.components.theme import eyebrow
from process_agent.ui.state import reset_dataset
from process_agent.ui.views.automation import render_automation_tab
from process_agent.ui.views.decision_gate import render_gate_tab
from process_agent.ui.views.event_log import render_event_log_tab
from process_agent.ui.views.overview import render_overview_tab
from process_agent.ui.views.process_map import render_process_map_tab
from process_agent.ui.views.roi import render_roi_tab


def _sidebar(df: pd.DataFrame, settings: Settings) -> None:
    with st.sidebar:
        st.markdown("### :material/hub: Process intelligence")
        with st.container(border=True):
            st.caption("Dataset")
            st.markdown(f"**{st.session_state.source_label}**")
            ts = pd.to_datetime(df["timestamp"], utc=True)
            st.caption(f"{df['case_id'].nunique():,} cases · {len(df):,} events  \n"
                       f"{ts.min():%d %b %Y} → {ts.max():%d %b %Y}")
            st.button("Load different data", icon=":material/swap_horiz:",
                      on_click=reset_dataset, width="stretch", key="btn_reset")

        st.markdown("**Analysis settings**")
        st.slider("Bottlenecks to flag", 1, 5, 3, key="bottleneck_top_n",
                  help="The N activities with the highest duration variance.")
        st.slider("Consistency threshold (CV)", 0.10, 0.60, 0.30, 0.05, key="cv_threshold",
                  help="Steps whose coefficient of variation (std ÷ mean) is at or "
                       "below this are treated as consistent enough to automate.")

        st.markdown("**AI agent**")
        if settings.live_llm:
            st.badge(f"Live · {settings.groq_model}", icon=":material/bolt:", color="green")
        else:
            st.badge("Deterministic mode", icon=":material/rule:", color="gray")
            st.caption("Add `GROQ_API_KEY` to secrets for LLM-enhanced advice.")


def render_workspace(settings: Settings) -> None:
    df: pd.DataFrame = st.session_state.df
    _sidebar(df, settings)
    a = analyse(df, settings)

    eyebrow("Process intelligence workspace")
    st.markdown("# How your process really runs")
    st.caption(f"{st.session_state.source_label} · {len(a.cases):,} cases · "
               f"{a.pm.graph.number_of_nodes()} activities · "
               f"{a.pm.graph.number_of_edges()} transitions")

    tabs = st.tabs([
        ":material/insights: Overview",
        ":material/account_tree: Process map",
        ":material/bolt: Automation",
        ":material/verified_user: Decision gate",
        ":material/savings: Impact & ROI",
        ":material/table_view: Event log",
    ])
    with tabs[0]:
        render_overview_tab(df, a)
    with tabs[1]:
        render_process_map_tab(a)
    with tabs[2]:
        render_automation_tab(a.advice, a.pm)
    with tabs[3]:
        render_gate_tab(settings, df, sorted(a.pm.activity_stats))
    with tabs[4]:
        render_roi_tab(df, a.cases, a.advice)
    with tabs[5]:
        render_event_log_tab(df)

"""
src/process_agent/ui/views/landing.py

Landing page shown before any data is loaded: hero (with live numbers from
the demo dataset), data entry points, how-it-works and the CSV format.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from process_agent.mining import analytics
from process_agent.mining.automation_advisor import get_automation_advice
from process_agent.mining.process_mining import discover_process_map
from process_agent.ui.components.theme import eyebrow, hero, numbered_steps, stat_strip
from process_agent.ui.state import (
    DEMO_CASES,
    demo_log,
    load_demo,
    load_upload,
    sample_csv_bytes,
)

_FORMAT = pd.DataFrame(
    [
        ("case_id", "Required", "CASE-00042", "Case ID, Ticket, Trace ID"),
        ("activity", "Required", "manager_approval", "Task, Step, Event, Action"),
        ("timestamp", "Required", "2024-01-15 09:30:00", "Time, Start time, Date"),
        ("duration_seconds", "Optional*", "3600", "Duration, Elapsed, Time taken"),
        ("variant", "Optional", "happy_path", "Path, Flow"),
        ("amount", "Optional", "450.00", "Value, Cost, Total"),
        ("submitter_id", "Optional", "EMP-042", "User, Resource, Employee ID"),
    ],
    columns=["Column", "Needed", "Example", "Also recognised as"],
)

_STEPS = [
    ("Discover the real process",
     "Reconstruct the as-executed flow from raw events — every path, loop and "
     "hand-off, with frequencies and waiting times. No assumptions, no workshops."),
    ("Diagnose where value leaks",
     "Pinpoint bottlenecks, rework loops and unpredictable steps, score process "
     "health from 0 to 100 and get findings written in plain language."),
    ("Automate with a safety gate",
     "Every recommendation comes with its ROI, and every AI-proposed action passes "
     "a deterministic confidence and policy gate with a full audit trail."),
]


@st.cache_data(show_spinner=False)
def _demo_snapshot() -> dict[str, str]:
    """Headline numbers computed live from the demo dataset."""
    df = demo_log(DEMO_CASES)
    pm = discover_process_map(df)
    cases = analytics.case_table(df)
    advice = get_automation_advice(pm)
    auto = {a.activity: a.estimated_saving_pct for a in advice if a.status == "automatable"}
    roi = analytics.estimate_roi(df, cases, auto, adoption=0.8)
    health = analytics.health_score(cases, pm)
    return {
        "paths": f"{cases['path'].nunique()}",
        "rework": f"{cases['has_rework'].mean():.0%}",
        "auto": f"{len(auto)} of {len(advice)}",
        "hours": f"{roi.hours_saved * roi.annual_factor:,.0f}",
        "health": f"{health.score}/100",
        "events": f"{len(df):,}",
    }


def _entry_cards() -> None:
    demo, upload = st.columns([1, 1.25], gap="medium")
    with demo.container(border=True, height="stretch"):
        eyebrow("Try it now")
        st.markdown("### Explore the demo")
        st.write(
            f"{DEMO_CASES:,} synthetic expense-reimbursement cases across four "
            "paths: happy path, finance escalation, rejection loop and missing "
            "receipt exception."
        )
        st.button(
            "Analyse demo dataset",
            icon=":material/arrow_forward:",
            type="primary",
            on_click=load_demo,
            key="btn_demo",
        )
    with upload.container(border=True):
        eyebrow("Your data")
        st.markdown("### Analyse your own event log")
        st.file_uploader(
            "Event log CSV",
            type=["csv"],
            key="csv_uploader",
            on_change=load_upload,
            label_visibility="collapsed",
        )
        with st.container(horizontal=True, vertical_alignment="center"):
            st.caption(
                "Columns are auto-detected. Only case ID, activity and timestamp are "
                "required — durations are derived from timestamps if missing."
            )
            st.download_button(
                "Sample CSV",
                data=sample_csv_bytes(),
                file_name="sample_event_log.csv",
                mime="text/csv",
                icon=":material/download:",
                type="tertiary",
                key="dl_sample",
            )


def _upload_feedback() -> None:
    errors = st.session_state.upload_errors
    if not errors:
        return
    st.error(
        "**We couldn't analyse that file.**\n\n" + "\n".join(f"- {e}" for e in errors),
        icon=":material/error:",
    )
    if st.session_state.ingest_mapping:
        st.caption(f"Detected column mapping: `{st.session_state.ingest_mapping}`")


def render_landing() -> None:
    snap = _demo_snapshot()
    hero(
        "Process intelligence · Agentic automation",
        "See how work really flows,",
        "then automate what's safe.",
        "Mine the true process from event logs, surface bottlenecks and rework, "
        "quantify automation ROI — and keep every AI action behind a deterministic "
        "decision gate.",
        [("Process health", snap["health"]), ("Automatable steps", snap["auto"]),
         ("Rework rate", snap["rework"]), ("Events mined", snap["events"])],
    )
    st.space("medium")
    _upload_feedback()
    _entry_cards()

    st.space("large")
    eyebrow("In the demo dataset")
    stat_strip([
        (snap["paths"], "distinct process paths discovered"),
        (snap["rework"], "of cases loop back for rework"),
        (snap["hours"], "handling hours / year ready to automate"),
    ])

    st.space("large")
    eyebrow("How it works")
    st.markdown("## From raw events to governed automation")
    numbered_steps(_STEPS)

    st.space("medium")
    with st.expander("Expected CSV format", icon=":material/table_view:"):
        st.dataframe(_FORMAT, hide_index=True, width="stretch")
        st.caption("*If `duration_seconds` is absent, each event lasts until the next "
                   "event in its case.")

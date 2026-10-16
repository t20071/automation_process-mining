"""
src/process_agent/ui/views/roi.py

Impact & ROI tab: user-adjustable assumptions -> annualised labour saving,
hours freed, cases touched and cycle-time impact of automation.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from process_agent.mining import analytics
from process_agent.mining.automation_advisor import ActivityAdvice
from process_agent.ui.components import charts
from process_agent.ui.components.theme import STATUS

_CURRENCIES = {"GBP": "£", "USD": "$", "EUR": "€", "INR": "₹"}


def _assumptions() -> dict:
    with st.container(border=True):
        st.markdown("**:material/tune: Assumptions** — adjust to your organisation")
        c1, c2, c3 = st.columns([1, 1, 2], gap="medium")
        currency = c1.selectbox("Currency", list(_CURRENCIES), key="roi_ccy")
        rate = c2.number_input("Loaded hourly cost", 1.0, 1_000.0, 30.0, 5.0, key="roi_rate")
        c4, c5 = st.columns([2, 2], gap="medium")
        minutes = c4.slider("Handling time saved per step (min)", 0.5, 30.0, 2.0, 0.5,
                            key="roi_minutes")
        adoption = c5.slider("Automation adoption", 10, 100, 80, 5, format="%d%%",
                             key="roi_adoption",
                             help="Share of eligible executions actually automated") / 100
        scope = c3.segmented_control(
            "Scope", ["automatable", "assisted"], default="automatable", required=True,
            key="roi_scope",
            format_func={"automatable": "Automatable only",
                         "assisted": "+ assisted review"}.get,
            help="'Assisted review' also applies workflow tooling to human-review "
                 "steps (approvals stay human).")
    return {"symbol": _CURRENCIES[currency], "rate": rate, "minutes": minutes,
            "adoption": adoption, "scope": scope}


def _saving_map(advice: list[ActivityAdvice], scope: str) -> dict[str, float]:
    allowed = {"automatable"} | ({"review"} if scope == "assisted" else set())
    return {a.activity: a.estimated_saving_pct for a in advice if a.status in allowed}


def _per_activity(df: pd.DataFrame, advice: list[ActivityAdvice], saving: dict[str, float],
                  p: dict) -> pd.DataFrame:
    labels = {a.activity: STATUS[a.status]["label"] for a in advice}
    rows = []
    for act, pct in saving.items():
        ev = df[df["activity"] == act]
        rows.append({
            "activity": act, "status_label": labels.get(act, "Other"),
            "hours_saved": len(ev) * p["adoption"] * p["minutes"] / 60,
            "wait_days_saved": ev["duration_seconds"].sum() * pct * p["adoption"] / 86_400,
        })
    return pd.DataFrame(rows)


def render_roi_tab(df: pd.DataFrame, cases: pd.DataFrame, advice: list[ActivityAdvice]) -> None:
    st.subheader("Impact & ROI")
    p = _assumptions()
    saving = _saving_map(advice, p["scope"])
    if not saving:
        st.info("No activities qualify for automation at the current settings. "
                "Try raising the consistency threshold in the sidebar.",
                icon=":material/info:")
        return
    roi = analytics.estimate_roi(df, cases, saving, p["rate"], p["minutes"], p["adoption"])
    yearly = roi.annual_factor
    sym = p["symbol"]
    delta_days = roi.after_mean_days - roi.before_mean_days

    with st.container(horizontal=True):
        st.metric("Labour saving / year", f"{sym}{roi.labour_saving * yearly:,.0f}", border=True,
                  help=f"Annualised from a {roi.span_days:.0f}-day log")
        st.metric("Hours freed / year", f"{roi.hours_saved * yearly:,.0f}", border=True,
                  help=f"{roi.automated_executions:,} automated executions in the log period")
        st.metric("Cases touched", f"{roi.cases_touched_pct:.0%}", border=True,
                  help=f"{roi.cases_touched:,} cases include at least one automated step")
        st.metric("Avg cycle time", f"{roi.after_mean_days:.2f} d", f"{delta_days:+.2f} d",
                  delta_color="inverse", border=True,
                  help=f"Before: {roi.before_mean_days:.2f} d per case")

    rows = _per_activity(df, advice, saving, p)
    c1, c2 = st.columns(2, gap="medium")
    with c1.container(border=True):
        st.markdown("**Handling hours freed** (log period)")
        st.altair_chart(charts.savings_chart(rows, "hours_saved", "Hours"), width="stretch")
    with c2.container(border=True):
        st.markdown("**Waiting time removed** (case-days, log period)")
        st.altair_chart(charts.savings_chart(rows, "wait_days_saved", "Case-days"),
                        width="stretch")
    st.caption("Estimates, not guarantees: savings use the advisor's per-step saving "
               "percentages and your assumptions above, applied to the uploaded log and "
               "annualised linearly. Validate with a pilot before committing budget.")

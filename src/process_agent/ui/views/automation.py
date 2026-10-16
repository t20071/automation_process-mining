"""
src/process_agent/ui/views/automation.py

Automation tab: per-activity classification (automatable / human review /
bottleneck) with the reasoning, implementation approach and tooling.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from process_agent.mining import analytics
from process_agent.mining.automation_advisor import ActivityAdvice
from process_agent.mining.process_mining import ProcessMap
from process_agent.ui.components.theme import STATUS, status_badge

# ---------------------------------------------------------------------------
# Automation tab
# ---------------------------------------------------------------------------


def _advice_card(adv: ActivityAdvice, pm: ProcessMap) -> None:
    s = pm.activity_stats.get(adv.activity)
    source = (":violet-badge[:material/auto_awesome: AI-enhanced]" if adv.source == "llm"
              else ":gray-badge[:material/rule: Rule-based]")
    with st.container(border=True):
        title = adv.activity.replace("_", " ").capitalize()
        st.markdown(f"#### {title} &nbsp; {status_badge(adv.status)} {source}")
        if s:
            st.caption(f"{s.count:,} executions · avg {analytics.fmt_duration(s.mean_seconds)} · "
                       f"P95 {analytics.fmt_duration(s.p95_seconds)}")
        why, how = st.columns(2, gap="medium")
        with why:
            st.markdown("**Why**")
            st.write(adv.reason)
        with how:
            st.markdown("**How to automate**")
            st.write(adv.how_to_automate)
        st.markdown(" ".join(f":gray-badge[{t}]" for t in adv.tools_suggested))
        st.progress(min(max(adv.estimated_saving_pct, 0.0), 1.0),
                    text=f"Estimated time saving on this step: "
                         f"**{adv.estimated_saving_pct:.0%}**")


def _guide_csv(advice: list[ActivityAdvice]) -> bytes:
    return pd.DataFrame([{
        "Activity": a.activity, "Status": a.status_label, "Reason": a.reason,
        "How to Automate": a.how_to_automate, "Tools": ", ".join(a.tools_suggested),
        "Estimated Saving %": f"{a.estimated_saving_pct:.0%}", "Source": a.source,
    } for a in advice]).to_csv(index=False).encode()


def render_automation_tab(advice: list[ActivityAdvice], pm: ProcessMap) -> None:
    counts = {k: sum(1 for a in advice if a.status == k) for k in STATUS}
    st.subheader("Automation advisor")
    st.caption("Each activity is classified from its duration statistics *and* what it "
               "means — approvals keep a human in the loop, exceptions are fixed upstream.")
    with st.container(horizontal=True):
        for key, meta in STATUS.items():
            st.metric(f"{meta['label']}", counts[key], border=True,
                      help=f"Activities classified as {meta['label'].lower()}")
        avg = sum(a.estimated_saving_pct for a in advice if a.status == "automatable")
        st.metric("Avg saving · automatable", f"{avg / max(counts['automatable'], 1):.0%}",
                  border=True)

    with st.container(horizontal=True, vertical_alignment="center"):
        choice = st.segmented_control(
            "Filter", ["all", *STATUS], default="all", required=True, key="advice_filter",
            format_func=lambda k: f"All ({len(advice)})" if k == "all"
            else f"{STATUS[k]['label']} ({counts[k]})",
            label_visibility="collapsed")
        st.space("stretch")
        st.download_button("Download guide (CSV)", _guide_csv(advice), "automation_guide.csv",
                           "text/csv", icon=":material/download:", type="tertiary")

    shown = [a for a in advice if choice == "all" or a.status == choice]
    for adv in shown:
        _advice_card(adv, pm)
    if not shown:
        st.caption("No activities match this filter.")

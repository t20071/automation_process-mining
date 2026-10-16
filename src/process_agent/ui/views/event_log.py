"""
src/process_agent/ui/views/event_log.py

Event-log tab: data-quality summary and a filterable view of raw events.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st


def _quality(df: pd.DataFrame) -> None:
    ts = pd.to_datetime(df["timestamp"], utc=True)
    per_case = df.groupby("case_id").size()
    with st.container(horizontal=True):
        st.metric("Events", f"{len(df):,}", border=True)
        st.metric("Cases", f"{df['case_id'].nunique():,}", border=True)
        st.metric("Activities", f"{df['activity'].nunique():,}", border=True)
        st.metric("Events per case", f"{per_case.mean():.1f}", border=True,
                  help=f"Min {per_case.min()} · max {per_case.max()}")
        st.metric("Time span", f"{(ts.max() - ts.min()).days:,} days", border=True)
    for note in st.session_state.ingest_notes:
        st.caption(f":material/info: {note}")
    mapping = {k: v for k, v in st.session_state.ingest_mapping.items() if k != v}
    if mapping:
        st.caption("Column mapping: " + ", ".join(f"`{k}` → `{v}`" for k, v in mapping.items()))


def render_event_log_tab(df: pd.DataFrame) -> None:
    st.subheader("Event log")
    _quality(df)

    c1, c2 = st.columns([1, 2], gap="medium")
    case_query = c1.text_input("Find case", placeholder="e.g. CASE-00042", key="log_case")
    acts = c2.multiselect("Activities", sorted(df["activity"].unique()), key="log_acts",
                          placeholder="All activities")
    view = df
    if case_query:
        view = view[view["case_id"].str.contains(case_query, case=False, regex=False)]
    if acts:
        view = view[view["activity"].isin(acts)]

    st.caption(f"Showing {min(len(view), 2_000):,} of {len(view):,} matching events")
    st.dataframe(view.head(2_000), hide_index=True, width="stretch", column_config={
        "timestamp": st.column_config.DatetimeColumn("Timestamp", format="YYYY-MM-DD HH:mm"),
        "duration_seconds": st.column_config.NumberColumn("Duration (s)", format="%.0f"),
        "amount": st.column_config.NumberColumn("Amount", format="%.2f"),
    })
    st.download_button("Download cleaned log (CSV)", view.to_csv(index=False).encode(),
                       "event_log_clean.csv", "text/csv", icon=":material/download:",
                       type="tertiary")

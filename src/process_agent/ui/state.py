"""
src/process_agent/ui/state.py

Session-state initialisation and dataset loading callbacks.
All per-user state lives in st.session_state and is initialised here only.
"""

from __future__ import annotations

import uuid

import pandas as pd
import streamlit as st

from process_agent.generators.log_generator import generate_event_log
from process_agent.ingestion import normalise_event_log

DEMO_CASES = 2_000

_DEFAULTS: dict[str, object] = {
    "df": None,                 # canonical event log (DataFrame)
    "data_key": "",             # unique id per loaded dataset (cache key)
    "source_label": "",
    "ingest_notes": [],
    "ingest_mapping": {},
    "upload_errors": [],
    "gate_results": [],         # decisions made this session
}


def init_state() -> None:
    for key, value in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value.copy() if hasattr(value, "copy") else value


def _set_dataset(df: pd.DataFrame, label: str, notes: list[str], mapping: dict) -> None:
    st.session_state.df = df
    st.session_state.data_key = uuid.uuid4().hex
    st.session_state.source_label = label
    st.session_state.ingest_notes = notes
    st.session_state.ingest_mapping = mapping
    st.session_state.upload_errors = []
    st.session_state.gate_results = []


@st.cache_data(show_spinner=False, max_entries=4)
def demo_log(num_cases: int) -> pd.DataFrame:
    return generate_event_log(num_cases=num_cases, seed=42)


@st.cache_data(show_spinner=False)
def sample_csv_bytes() -> bytes:
    """A small downloadable sample in the expected format."""
    return generate_event_log(num_cases=20, seed=0).to_csv(index=False).encode()


def load_demo() -> None:
    """on_click callback: load the synthetic expense-reimbursement log."""
    _set_dataset(demo_log(DEMO_CASES), "Demo · expense reimbursement", [], {})


def load_upload() -> None:
    """on_change callback for the CSV uploader."""
    uploaded = st.session_state.get("csv_uploader")
    if uploaded is None:
        return
    try:
        raw = pd.read_csv(uploaded)
    except Exception as exc:  # malformed CSV, wrong encoding, etc.
        st.session_state.upload_errors = [f"Could not read `{uploaded.name}`: {exc}"]
        return
    result = normalise_event_log(raw)
    if not result.ok:
        st.session_state.upload_errors = result.errors
        st.session_state.ingest_mapping = result.mapping
        return
    _set_dataset(result.df, uploaded.name, result.notes, result.mapping)


def reset_dataset() -> None:
    """on_click callback: return to the landing page."""
    st.session_state.df = None
    st.session_state.data_key = ""
    st.session_state.gate_results = []
    st.session_state.upload_errors = []
    st.session_state.pop("csv_uploader", None)   # clear the uploader widget

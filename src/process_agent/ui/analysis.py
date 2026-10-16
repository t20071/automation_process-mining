"""
src/process_agent/ui/analysis.py

Bundles everything mined from the loaded event log into one ``Analysis``
object and caches it per dataset, so every view reads the same numbers.
Cache keys are a per-dataset id (not a hash of the DataFrame), which keeps
reruns fast and guarantees a newly uploaded file is never served stale results.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from process_agent.config import Settings
from process_agent.mining import analytics
from process_agent.mining.automation_advisor import ActivityAdvice, get_automation_advice
from process_agent.mining.process_mining import ProcessMap, discover_process_map


@dataclass
class Analysis:
    pm: ProcessMap
    cases: pd.DataFrame
    advice: list[ActivityAdvice]

    @property
    def status_by_activity(self) -> dict[str, str]:
        return {a.activity: a.status for a in self.advice}

    def activities_with(self, status: str) -> list[str]:
        return [a.activity for a in self.advice if a.status == status]


# ---------------------------------------------------------------------------
# Cached computation — keyed on a per-dataset id, not on hashing the frame
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="Mining the process…", max_entries=8)
def _mine(data_key: str, _df: pd.DataFrame, top_n: int, cv: float):
    pm = discover_process_map(_df, bottleneck_top_n=top_n, cv_threshold=cv)
    return pm, analytics.case_table(_df)


@st.cache_data(show_spinner="Generating automation advice…", max_entries=8)
def _advise(data_key: str, _df: pd.DataFrame, top_n: int, cv: float,
            groq_key: str, groq_model: str) -> list[ActivityAdvice]:
    pm = discover_process_map(_df, bottleneck_top_n=top_n, cv_threshold=cv)
    return get_automation_advice(pm, groq_api_key=groq_key, groq_model=groq_model)


def analyse(df: pd.DataFrame, settings: Settings) -> Analysis:
    key = st.session_state.data_key
    top_n = st.session_state.get("bottleneck_top_n", 3)
    cv = st.session_state.get("cv_threshold", 0.30)
    pm, cases = _mine(key, df, top_n, cv)
    groq_key = settings.groq_api_key if settings.live_llm else ""
    advice = _advise(key, df, top_n, cv, groq_key, settings.groq_model)
    return Analysis(pm, cases, advice)

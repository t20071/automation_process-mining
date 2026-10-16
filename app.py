"""
app.py — thin Streamlit entrypoint.

Responsibilities:
  - Page config + logging + settings
  - Landing page (demo data or CSV upload) until a dataset is loaded
  - Workspace (process mining, automation advice, decision gate, ROI)

Zero business logic lives here — all logic is in src/process_agent/.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on the Python path when running directly
sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st

from process_agent.ui.components.theme import configure_page, inject_css

configure_page()  # must be the first Streamlit call

from process_agent.config import get_settings  # noqa: E402
from process_agent.logging_config import setup_logging  # noqa: E402
from process_agent.ui.state import init_state  # noqa: E402
from process_agent.ui.views.landing import render_landing  # noqa: E402
from process_agent.ui.workspace import render_workspace  # noqa: E402

setup_logging()
settings = get_settings()
init_state()
inject_css()

if st.session_state.df is None:
    render_landing()
else:
    render_workspace(settings)

"""
src/process_agent/ui/theme.py

Injects the SKILL_webdesign.md color/type/spacing/motion token block into
the Streamlit app via st.markdown.  Call apply_theme() once at the top
of app.py before rendering any other content.
"""

from __future__ import annotations

import streamlit as st

_CSS_TOKENS = """
<style>
/* ================================================================
   Design tokens — from SKILL_webdesign.md
   ================================================================ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=DM+Serif+Display&display=swap');

:root {
  /* Color palette */
  --white: #ffffff;
  --night: #161714;
  --grape: #9677ff;
  --amethyst: #4e287a;
  --ocean: #e5f8ff;
  --sky: #97c8ff;
  --dusk: #6474cd;
  --raspberry: #985fca;
  --gray: #81837a;

  --midnight-25: #4a4b44;
  --midnight-50: #383a35;
  --midnight-75: #252622;
  --midnight-100: #21231e;

  --stone-25: #f7fbf5;
  --stone-50: #e7ebe5;
  --stone-75: #d8dad1;
  --stone-100: #c3c6bb;
  --sand-25: #f6f4f0;

  /* Semantic tokens */
  --background: var(--white);
  --foreground: var(--night);
  --accent: var(--grape);
  --accent-hover: var(--amethyst);
  --card: var(--stone-50);
  --card-hover: var(--stone-75);
  --border: var(--stone-50);
  --muted: color-mix(in srgb, var(--night) 60%, transparent);

  /* Type scale */
  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-base: 1rem;
  --text-lg: 1.125rem;

  /* Shape & spacing */
  --radius-xs: 0.125rem;
  --radius-sm: 0.25rem;
  --radius-md: 0.375rem;
  --radius-lg: 0.5rem;
  --radius-xl: 0.75rem;
  --radius-2xl: 1rem;
  --spacing: 0.25rem;

  /* Motion */
  --ease-out: cubic-bezier(0, 0, 0.2, 1);
  --transition: cubic-bezier(0.4, 0, 0.2, 1);
}

/* ================================================================
   Base reset & typography
   ================================================================ */
html, body, [class*="css"] {
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--night);
  background-color: var(--background);
}

h1, h2, h3 {
  font-family: 'DM Serif Display', ui-sans-serif, system-ui, sans-serif;
  letter-spacing: -0.025em;
  color: var(--night);
}

/* ================================================================
   Streamlit chrome overrides
   ================================================================ */
/* Hide default deploy/hamburger */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }

/* App container */
.block-container {
  padding-top: 2rem !important;
  padding-bottom: 2rem !important;
  max-width: 1100px;
}

/* Sidebar */
section[data-testid="stSidebar"] {
  background-color: var(--stone-25) !important;
  border-right: 1px solid var(--stone-100);
}

/* Tabs */
button[data-baseweb="tab"] {
  font-family: 'Inter', sans-serif !important;
  font-weight: 500 !important;
  font-size: var(--text-sm) !important;
  color: var(--gray) !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
  color: var(--grape) !important;
  border-bottom-color: var(--grape) !important;
}

/* Metric cards */
[data-testid="stMetric"] {
  background: var(--stone-50);
  border-radius: var(--radius-xl);
  padding: 1rem 1.25rem;
  border: 1px solid var(--stone-100);
  transition: background 150ms var(--ease-out);
}
[data-testid="stMetric"]:hover {
  background: var(--stone-75);
}
[data-testid="stMetricLabel"] p {
  font-size: var(--text-sm) !important;
  font-weight: 500 !important;
  color: var(--gray) !important;
  text-transform: uppercase;
  letter-spacing: 0.025em;
}
[data-testid="stMetricValue"] {
  font-size: 1.75rem !important;
  font-weight: 700 !important;
  color: var(--night) !important;
}

/* Buttons */
.stButton > button {
  font-family: 'Inter', sans-serif !important;
  font-weight: 600 !important;
  font-size: var(--text-sm) !important;
  border-radius: var(--radius-lg) !important;
  transition: all 150ms var(--ease-out) !important;
}
.stButton > button:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px color-mix(in srgb, var(--grape) 25%, transparent);
}

/* DataFrames */
.stDataFrame {
  border-radius: var(--radius-xl) !important;
  overflow: hidden;
  border: 1px solid var(--stone-100) !important;
}
</style>
"""

# ──────────────────────────────────────────────────────────────
# Custom HTML components (reusable by dashboard.py)
# ──────────────────────────────────────────────────────────────

def metric_card(label: str, value: str, sub: str = "", accent: bool = False) -> str:
    """Return an HTML metric card string."""
    accent_style = (
        f"border-left: 4px solid var(--grape);" if accent else ""
    )
    return f"""
    <div style="
        background: var(--stone-50);
        border-radius: var(--radius-xl);
        padding: 1.25rem 1.5rem;
        border: 1px solid var(--stone-100);
        {accent_style}
        transition: background 150ms var(--ease-out);
        margin-bottom: 0.5rem;
    ">
        <p style="font-size: var(--text-xs); font-weight: 600; color: var(--gray);
                  text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 0.25rem;">
            {label}
        </p>
        <p style="font-size: 1.75rem; font-weight: 700; color: var(--night); margin: 0 0 0.25rem;">
            {value}
        </p>
        {"<p style='font-size: var(--text-xs); color: var(--gray); margin: 0;'>" + sub + "</p>" if sub else ""}
    </div>
    """


def status_badge(decision: str) -> str:
    """Return a coloured status badge HTML string."""
    color_map = {
        "APPROVED": ("#d1fae5", "#065f46"),
        "DENIED": ("#fee2e2", "#991b1b"),
        "ESCALATED": ("#fef3c7", "#92400e"),
    }
    bg, fg = color_map.get(decision, ("#e7ebe5", "#161714"))
    return (
        f'<span style="display:inline-block; padding: 0.2rem 0.6rem; '
        f'border-radius: var(--radius-lg); background:{bg}; color:{fg}; '
        f'font-size: var(--text-xs); font-weight: 600; letter-spacing: 0.05em;">'
        f"{decision}</span>"
    )


def page_header(title: str, subtitle: str = "") -> str:
    """Return a styled page header HTML block."""
    sub_html = (
        f'<p style="font-size: var(--text-base); color: var(--gray); margin: 0.25rem 0 0;">'
        f"{subtitle}</p>"
        if subtitle
        else ""
    )
    return f"""
    <div style="margin-bottom: 2rem;">
        <h1 style="font-family: 'DM Serif Display', serif; font-size: 2rem;
                   letter-spacing: -0.025em; color: var(--night); margin: 0;">
            {title}
        </h1>
        {sub_html}
        <div style="height: 3px; width: 3rem; background: var(--grape);
                    border-radius: var(--radius-xs); margin-top: 0.75rem;"></div>
    </div>
    """


def section_header(text: str) -> str:
    return (
        f'<h2 style="font-family: \'DM Serif Display\', serif; font-size: 1.35rem; '
        f'letter-spacing: -0.02em; color: var(--night); margin: 1.5rem 0 0.75rem;">'
        f"{text}</h2>"
    )


def apply_theme() -> None:
    """Inject CSS tokens and page config into the Streamlit app."""
    st.set_page_config(
        page_title="Process Intelligence Engine",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(_CSS_TOKENS, unsafe_allow_html=True)

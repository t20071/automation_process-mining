"""
src/process_agent/ui/components/theme.py

Design tokens and presentational helpers (see docs/design-system.md).

Colours, fonts and radii for native widgets live in .streamlit/config.toml.
This module holds the Python-side constants used by charts and the process
map, plus a few custom HTML blocks native Streamlit can't express: the
landing hero, eyebrow labels, bracketed stats and numbered feature columns.
Visual language: editorial enterprise — light grotesk display type, small
uppercase eyebrows marked with a grape square, corner-bracket stat frames.
"""

from __future__ import annotations

import html

import streamlit as st

# ── Brand tokens (docs/design-system.md) ───────────────────────────────────────
NIGHT = "#161714"
GRAPE = "#9677ff"
AMETHYST = "#4e287a"
DUSK = "#6474cd"
GRAY = "#81837a"
STONE_25 = "#f7fbf5"
STONE_50 = "#e7ebe5"
STONE_100 = "#c3c6bb"

# ── Status palette (validated for colour-vision deficiency) ────────────────
# Each status pairs a strong mark colour with a light tint for node fills.
STATUS = {
    "automatable": {"label": "Automatable", "color": "#2d9bc4", "tint": "#e1f2f9",
                    "icon": ":material/bolt:", "badge": "blue"},
    "review":      {"label": "Human review", "color": "#8b6cf5", "tint": "#efebfe",
                    "icon": ":material/person_check:", "badge": "violet"},
    "bottleneck":  {"label": "Bottleneck", "color": "#d6645a", "tint": "#fbe6e3",
                    "icon": ":material/hourglass_top:", "badge": "red"},
}

DECISION = {
    "APPROVED":  {"badge": "green", "icon": ":material/check_circle:"},
    "DENIED":    {"badge": "red", "icon": ":material/block:"},
    "ESCALATED": {"badge": "orange", "icon": ":material/support_agent:"},
}

_CSS = """
<style>
/* Metric numerals: light, tight display type */
[data-testid="stMetricValue"] {
  font-family: 'Inter Tight', 'Inter', sans-serif; font-weight: 400;
  letter-spacing: -0.03em;
}
[data-testid="stMetricLabel"] p {
  text-transform: uppercase; letter-spacing: .06em; font-size: .72rem; font-weight: 600;
}
h1, h2, h3 { letter-spacing: -0.03em; }

/* Eyebrow label: ■ SMALL UPPERCASE */
.pi-eyebrow {
  display: flex; align-items: center; gap: .75rem; margin: .25rem 0 .1rem;
  font: 600 .72rem/1 'Inter', sans-serif; letter-spacing: .1em; text-transform: uppercase;
  color: #161714;
}
.pi-eyebrow::before { content: ""; width: 7px; height: 7px; background: #9677ff; }

/* Corner-bracket frame */
.pi-bracket { position: relative; padding: .35rem .7rem; display: inline-block; }
.pi-bracket::before, .pi-bracket::after {
  content: ""; position: absolute; width: 9px; height: 100%; top: 0;
  border: 1.5px solid currentColor; opacity: .55;
}
.pi-bracket::before { left: 0; border-right: none; }
.pi-bracket::after { right: 0; border-left: none; }

/* Stat strip */
.pi-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  border-top: 1px solid #e7ebe5; border-bottom: 1px solid #e7ebe5; }
.pi-stat { display: flex; align-items: center; gap: 1rem; padding: 1.4rem .25rem; color: #161714; }
.pi-stat .num { font: 400 2.1rem/1 'Inter Tight', 'Inter', sans-serif; letter-spacing: -.04em; }
.pi-stat .lbl { font-size: .9rem; color: #4a4b44; line-height: 1.3; }

/* Numbered feature columns */
.pi-steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  border-top: 1px solid #e7ebe5; border-bottom: 1px solid #e7ebe5; }
.pi-step { padding: 2rem 1.75rem 2.25rem 0; }
.pi-step + .pi-step { border-left: 1px solid #e7ebe5; padding-left: 1.75rem; }
.pi-step .n { font: 400 1.6rem/1 'Inter Tight', 'Inter', sans-serif; color: #9677ff; }
.pi-step h4 { font: 400 1.45rem/1.2 'Inter Tight', 'Inter', sans-serif; letter-spacing: -.03em;
  margin: 1.4rem 0 .9rem; padding: 0; color: #161714; }
.pi-step p { color: #4a4b44; font-size: .95rem; line-height: 1.6; margin: 0; }
@media (max-width: 640px) { .pi-step + .pi-step { border-left: none; padding-left: 0;
  border-top: 1px solid #e7ebe5; } }

/* Flow strip: numbered pipeline with gradient rail */
.pi-flow { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  border: 1px solid #e7ebe5; border-radius: 6px; overflow: hidden; position: relative; }
.pi-flow > div { padding: 1.1rem 1.1rem 1.4rem; background: #fff; }
.pi-flow > div + div { border-left: 1px solid #e7ebe5; }
.pi-flow .n { font: 400 .95rem/1 'Inter Tight', 'Inter', sans-serif; color: #9677ff; }
.pi-flow .t { font-weight: 600; margin: .55rem 0 .25rem; color: #161714; font-size: .95rem; }
.pi-flow .s { color: #4a4b44; font-size: .82rem; line-height: 1.45; }
.pi-flow::after { content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 3px;
  background: linear-gradient(90deg, #9677ff, #6474cd 60%, #4e287a); }

/* Hero */
.pi-hero { position: relative; overflow: hidden; border-radius: 6px; color: #f7fbf5;
  padding: 4.5rem 3rem 3.5rem;
  background:
    linear-gradient(rgba(255,255,255,.045) 1px, transparent 1px) 0 0 / 56px 56px,
    linear-gradient(90deg, rgba(255,255,255,.045) 1px, transparent 1px) 0 0 / 56px 56px,
    radial-gradient(900px 420px at 95% 0%, rgba(150,119,255,.35), transparent 60%),
    radial-gradient(700px 300px at 0% 100%, rgba(100,116,205,.28), transparent 60%),
    #161714;
  display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); gap: 2.5rem; }
.pi-hero h1 { font: 400 clamp(2.2rem, 4.4vw, 3.6rem)/1.04 'Inter Tight', 'Inter', sans-serif;
  letter-spacing: -.04em; margin: 0 0 1.25rem; padding: 0; color: #fff; }
.pi-hero h1 .dim { color: rgba(247,251,245,.55); }
.pi-hero .lede { font-size: 1.05rem; line-height: 1.6; color: rgba(247,251,245,.75);
  max-width: 34rem; margin: 0; }
.pi-hero .tag { display: inline-flex; align-items: center; gap: .6rem; margin-bottom: 1.5rem;
  font: 600 .7rem/1 'Inter', sans-serif; letter-spacing: .12em; text-transform: uppercase;
  color: #c9b9ff; }
.pi-hero .tag::before { content: ""; width: 7px; height: 7px; background: #9677ff; }
.pi-hero .panel { position: relative; align-self: center; min-height: 250px;
  border: 1px solid rgba(247,251,245,.16); }
.pi-hero .panel::before { content: ""; position: absolute; inset: 22% 30% 34% 18%;
  border: 1px solid rgba(247,251,245,.12); }
.pi-hero .chip { position: absolute; font: 600 .68rem/1 'Inter', sans-serif;
  letter-spacing: .08em; text-transform: uppercase; color: #f7fbf5; white-space: nowrap;
  background: rgba(22,23,20,.55); backdrop-filter: blur(2px); padding: .55rem .8rem; }
.pi-hero .chip b { color: #c9b9ff; font-weight: 600; margin-left: .5rem; }
.pi-hero .bar { position: absolute; left: 0; right: 0; bottom: 0; height: 4px;
  background: linear-gradient(90deg, #9677ff, #6474cd 60%, #4e287a); }
@media (max-width: 760px) { .pi-hero { grid-template-columns: 1fr; padding: 2.5rem 1.25rem; }
  .pi-hero .panel { min-height: 200px; } }
</style>
"""

_CHIP_POS = ["top:8%;left:6%", "top:40%;right:6%", "bottom:12%;left:22%", "bottom:38%;left:4%"]


def configure_page() -> None:
    """Set page config. Must be the first Streamlit call."""
    st.set_page_config(
        page_title="Process Intelligence Engine",
        page_icon=":material/hub:",
        layout="wide",
        initial_sidebar_state="auto",
    )


def inject_css() -> None:
    """Inject the small custom stylesheet (once per run)."""
    st.html(_CSS)


def status_badge(status: str) -> str:
    """Inline Markdown badge for an advisor status."""
    meta = STATUS.get(status, {"badge": "gray", "label": status, "icon": ""})
    return f":{meta['badge']}-badge[{meta['icon']} {meta['label']}]"


def decision_badge(decision: str) -> str:
    """Inline Markdown badge for a gate decision."""
    meta = DECISION.get(decision, {"badge": "gray", "icon": ""})
    return f":{meta['badge']}-badge[{meta['icon']} {decision}]"


def eyebrow(text: str) -> None:
    """Small uppercase section label with a grape square marker."""
    st.html(f'<div class="pi-eyebrow">{html.escape(text)}</div>')


def hero(tag: str, dim: str, bright: str, lede: str, chips: list[tuple[str, str]]) -> None:
    """Dark hero: two-tone headline left, bracketed live-stat chips right."""
    chip_html = "".join(
        f'<span class="chip pi-bracket" style="{pos}">{html.escape(k)}<b>{html.escape(v)}</b></span>'
        for (k, v), pos in zip(chips, _CHIP_POS)
    )
    st.html(f"""
    <div class="pi-hero">
      <div>
        <div class="tag">{html.escape(tag)}</div>
        <h1><span class="dim">{html.escape(dim)}</span> {html.escape(bright)}</h1>
        <p class="lede">{html.escape(lede)}</p>
      </div>
      <div class="panel">{chip_html}</div>
      <div class="bar"></div>
    </div>""")


def stat_strip(stats: list[tuple[str, str]]) -> None:
    """Row of bracketed headline numbers with labels."""
    cells = "".join(
        f'<div class="pi-stat"><span class="num pi-bracket">{html.escape(n)}</span>'
        f'<span class="lbl">{html.escape(label)}</span></div>'
        for n, label in stats
    )
    st.html(f'<div class="pi-stats">{cells}</div>')


def flow_strip(steps: list[tuple[str, str]]) -> None:
    """Compact numbered pipeline (title, subtitle) with a gradient rail."""
    cells = "".join(
        f'<div><div class="n">{i:02d}</div><div class="t">{html.escape(t)}</div>'
        f'<div class="s">{html.escape(s)}</div></div>'
        for i, (t, s) in enumerate(steps, start=1)
    )
    st.html(f'<div class="pi-flow">{cells}</div>')


def numbered_steps(steps: list[tuple[str, str]]) -> None:
    """01 / 02 / 03 feature columns separated by hairlines."""
    cells = "".join(
        f'<div class="pi-step"><div class="n">{i:02d}</div><h4>{html.escape(t)}</h4>'
        f'<p>{html.escape(body)}</p></div>'
        for i, (t, body) in enumerate(steps, start=1)
    )
    st.html(f'<div class="pi-steps">{cells}</div>')

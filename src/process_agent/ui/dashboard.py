"""
src/process_agent/ui/dashboard.py

Dashboard rendering logic.  Imported and called by app.py.
No business logic here — only presentation.

Tabs
----
1. Process Map      — DFG visualisation + cycle-time table
2. Automation Guide — per-activity: status, WHY, HOW, tools
3. Gate Demo        — live gate engine decisions (A/B/C scenarios)
4. Metrics & ROI    — before/after cycle time, % automated, ROI estimate
"""

from __future__ import annotations

import io
import logging
from typing import Any

import matplotlib
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import streamlit as st

from process_agent.mining.automation_advisor import ActivityAdvice
from process_agent.mining.process_mining import ProcessMap, cycle_time_summary
from process_agent.ui.theme import metric_card, section_header, status_badge

matplotlib.use("Agg")

logger = logging.getLogger(__name__)

# ── Design tokens (mirrors SKILL_webdesign.md) ──────────────────────────────
_GRAPE      = "#9677ff"
_AMETHYST   = "#4e287a"
_SKY        = "#97c8ff"
_DUSK       = "#6474cd"
_NIGHT      = "#161714"
_STONE_50   = "#e7ebe5"
_STONE_75   = "#d8dad1"
_STONE_100  = "#c3c6bb"
_GRAY       = "#81837a"
_WHITE      = "#ffffff"

# Status colours
_STATUS_COLORS = {
    "automatable": ("#d1fae5", "#065f46"),   # green
    "review":      ("#fef3c7", "#92400e"),   # amber
    "bottleneck":  ("#fee2e2", "#991b1b"),   # red
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _fmt(seconds: float) -> str:
    if seconds < 60:    return f"{seconds:.0f}s"
    if seconds < 3_600: return f"{seconds / 60:.0f}m"
    if seconds < 86_400:return f"{seconds / 3_600:.1f}h"
    return f"{seconds / 86_400:.1f}d"


# ── DFG visualisation ────────────────────────────────────────────────────────

def _hierarchical_layout(G: nx.DiGraph) -> dict:
    """Topological left-to-right layout when Graphviz is unavailable."""
    try:
        levels: dict = {}
        for node in nx.topological_sort(G):
            preds = list(G.predecessors(node))
            levels[node] = 0 if not preds else max(levels.get(p, 0) for p in preds) + 1
        level_groups: dict = {}
        for node, lvl in levels.items():
            level_groups.setdefault(lvl, []).append(node)
        max_lvl = max(level_groups) if level_groups else 0
        max_per = max(len(v) for v in level_groups.values()) if level_groups else 1
        pos: dict = {}
        for lvl, nodes in level_groups.items():
            x = lvl / max(max_lvl, 1) * 100
            for i, node in enumerate(nodes):
                y = (i - (len(nodes) - 1) / 2) / max(max_per, 1) * 100
                pos[node] = (x, y)
        return pos
    except Exception:
        return nx.spring_layout(G, seed=42, k=3.0)


def _draw_dfg(process_map: ProcessMap) -> io.BytesIO:
    """High-resolution DFG renderer (300 DPI).

    Nodes: FancyBboxPatch rounded rectangles with dual-line labels
    (activity name + avg duration; bottlenecks also show stddev).
    Edges scaled by frequency (width + opacity).
    """
    G           = process_map.graph
    bottlenecks = set(process_map.bottlenecks)
    automatable = set(process_map.automatable_steps)
    act_stats   = process_map.activity_stats

    # Layout
    try:
        raw_pos = nx.nx_agraph.graphviz_layout(
            G, prog="dot", args="-Grankdir=LR -Gnodesep=0.8 -Granksep=1.8"
        )
    except Exception:
        raw_pos = _hierarchical_layout(G)

    # Normalise canvas: x in [1.2, 10.8], y in [0.8, 7.2]
    xs = [p[0] for p in raw_pos.values()]
    ys = [p[1] for p in raw_pos.values()]
    xr = max(max(xs) - min(xs), 1)
    yr = max(max(ys) - min(ys), 1)
    pos = {
        n: (1.2 + (p[0] - min(xs)) / xr * 9.6,
            0.8 + (p[1] - min(ys)) / yr * 6.4)
        for n, p in raw_pos.items()
    }

    # Figure
    fig, ax = plt.subplots(figsize=(20, 9), facecolor=_WHITE)
    ax.set_facecolor(_WHITE)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.set_aspect("equal")
    ax.axis("off")

    NODE_W, NODE_H = 1.20, 0.68

    # Edges
    max_freq = max(
        (d.get("frequency", 1) for _, _, d in G.edges(data=True)), default=1
    )
    for src, tgt, data in G.edges(data=True):
        freq  = data.get("frequency", 1)
        dur   = data.get("mean_duration", 0)
        lw    = 1.2 + 3.8 * (freq / max_freq)
        alpha = 0.35 + 0.65 * (freq / max_freq)
        sx, sy = pos[src]
        tx, ty = pos[tgt]
        ax.annotate(
            "",
            xy=(tx - NODE_W / 2, ty),
            xytext=(sx + NODE_W / 2, sy),
            arrowprops=dict(
                arrowstyle="-|>",
                color=_DUSK, lw=lw, alpha=alpha,
                connectionstyle="arc3,rad=0.08",
                mutation_scale=20,
            ),
            zorder=2,
        )
        ax.text(
            (sx + tx) / 2, (sy + ty) / 2 + 0.12, _fmt(dur),
            ha="center", va="bottom", fontsize=6.5, color=_GRAY, zorder=3,
            bbox=dict(boxstyle="round,pad=0.25", facecolor=_WHITE,
                      edgecolor="none", alpha=0.90),
        )

    # Nodes as rounded rectangles
    for node in G.nodes():
        x, y = pos[node]
        if node in bottlenecks:
            face, border, tc = _GRAPE, _AMETHYST, _WHITE
        elif node in automatable:
            face, border, tc = _SKY, _DUSK, _NIGHT
        else:
            face, border, tc = _STONE_50, _STONE_100, _NIGHT

        ax.add_patch(mpatches.FancyBboxPatch(
            (x - NODE_W / 2, y - NODE_H / 2), NODE_W, NODE_H,
            boxstyle="round,pad=0.06",
            facecolor=face, edgecolor=border, linewidth=1.8, zorder=4,
        ))

        ax.text(x, y + 0.10, node.replace("_", " "),
                ha="center", va="center",
                fontsize=8, fontweight="bold", color=tc, zorder=5)

        s = act_stats.get(node)
        if s:
            sub = f"avg {_fmt(s.mean_seconds)}"
            if node in bottlenecks:
                sub += f"  ±{_fmt(s.std_seconds)}"
            ax.text(x, y - 0.16, sub,
                    ha="center", va="center", fontsize=6.0,
                    color=_WHITE if node in bottlenecks else _GRAY,
                    alpha=0.90, zorder=5)

    # Legend
    legend_patches = [
        mpatches.Patch(facecolor=_GRAPE,    edgecolor=_AMETHYST, lw=1.5, label="🔴  Bottleneck"),
        mpatches.Patch(facecolor=_SKY,      edgecolor=_DUSK,     lw=1.5, label="✅  Automatable"),
        mpatches.Patch(facecolor=_STONE_50, edgecolor=_STONE_100,lw=1.5, label="Standard"),
    ]
    leg = ax.legend(handles=legend_patches, loc="upper left",
                    framealpha=0.95, fontsize=9, edgecolor=_STONE_100,
                    fancybox=True, frameon=True, borderpad=0.8, labelspacing=0.6)
    leg.get_frame().set_linewidth(1.0)

    ax.set_title(
        "Directly-Follows Graph (DFG)  —  edge width ∝ case frequency",
        fontsize=12, color=_NIGHT, fontweight="700", pad=16,
    )

    plt.tight_layout(pad=1.2)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight", facecolor=_WHITE)
    buf.seek(0)
    plt.close(fig)
    return buf



# ── Tab 1: Process Map ───────────────────────────────────────────────────────

def render_process_map_tab(process_map: ProcessMap) -> None:
    st.markdown(section_header("Process Map (DFG)"), unsafe_allow_html=True)
    st.markdown(
        "<p style='color:var(--gray);font-size:0.875rem;margin-bottom:1rem;'>"
        "Edge labels show <strong>mean wait time</strong> between steps. "
        "Node colour: <span style='color:#9677ff;font-weight:600'>■ Bottleneck</span> · "
        "<span style='color:#97c8ff;font-weight:600'>■ Automatable</span></p>",
        unsafe_allow_html=True,
    )
    st.image(_draw_dfg(process_map), width="stretch")

    st.markdown(section_header("Cycle Time by Activity"), unsafe_allow_html=True)
    summary = cycle_time_summary(process_map)
    display = summary.copy()
    display["Mean"]  = display["mean_seconds"].apply(_fmt)
    display["Std"]   = display["std_seconds"].apply(_fmt)
    display["P95"]   = display["p95_seconds"].apply(_fmt)
    display = display[["activity","Mean","Std","P95","count","is_bottleneck","is_automatable"]]
    display.columns = ["Activity","Mean","Std Dev","P95","Cases","Bottleneck?","Automatable?"]
    st.dataframe(display, width="stretch", hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🔴 Top Bottlenecks** _(highest variance)_")
        for b in process_map.bottlenecks:
            s = process_map.activity_stats[b]
            st.markdown(f"- `{b}` — avg **{_fmt(s.mean_seconds)}**, std **{_fmt(s.std_seconds)}**")
    with col2:
        st.markdown("**✅ Automatable Steps** _(low variance, consistent)_")
        if process_map.automatable_steps:
            for a in process_map.automatable_steps:
                st.markdown(f"- `{a}`")
        else:
            st.markdown("_None identified at current CV threshold_")


# ── Tab 2: Automation Guide ──────────────────────────────────────────────────

def _advice_card(adv: ActivityAdvice) -> str:
    bg, fg = _STATUS_COLORS.get(adv.status, (_STONE_50, _NIGHT))
    saving_pct = int(adv.estimated_saving_pct * 100)
    tools_html = "".join(
        f'<span style="display:inline-block;margin:2px 4px 2px 0;padding:2px 8px;'
        f'background:var(--stone-75);border-radius:var(--radius-sm);'
        f'font-size:0.75rem;color:var(--night);">{t}</span>'
        for t in adv.tools_suggested
    )
    source_badge = (
        '<span style="font-size:0.7rem;color:var(--gray);float:right;">'
        + ("🤖 AI-enhanced" if adv.source == "llm" else "📐 Rule-based")
        + "</span>"
    )
    return f"""
    <div style="
        background:{bg};border-radius:var(--radius-xl);
        padding:1.25rem 1.5rem;margin-bottom:0.75rem;
        border-left:4px solid {fg};
    ">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.5rem;">
            <span style="font-weight:700;font-size:1rem;color:{_NIGHT};">
                {adv.status_emoji} &nbsp; <code style="background:rgba(0,0,0,0.06);
                padding:2px 6px;border-radius:4px;font-size:0.9rem;">{adv.activity}</code>
            </span>
            <span style="font-size:0.75rem;font-weight:600;
                         background:{fg};color:white;
                         padding:2px 10px;border-radius:999px;">
                {adv.status_label}
            </span>
        </div>
        <p style="font-size:0.85rem;color:var(--gray);margin:0 0 0.6rem;">
            <strong>Why:</strong> {adv.reason}
        </p>
        <p style="font-size:0.875rem;color:{_NIGHT};margin:0 0 0.6rem;">
            <strong>How to automate:</strong> {adv.how_to_automate}
        </p>
        <div style="margin-bottom:0.4rem;">{tools_html}</div>
        <div style="display:flex;align-items:center;justify-content:space-between;">
            <span style="font-size:0.75rem;color:var(--gray);">
                ⏱ Estimated time saving: <strong>{saving_pct}%</strong> of step duration
            </span>
            {source_badge}
        </div>
    </div>
    """


def render_automation_guide_tab(advice_list: list[ActivityAdvice]) -> None:
    st.markdown(section_header("Automation Guide"), unsafe_allow_html=True)

    # Summary counts
    auto_count  = sum(1 for a in advice_list if a.status == "automatable")
    review_count= sum(1 for a in advice_list if a.status == "review")
    bot_count   = sum(1 for a in advice_list if a.status == "bottleneck")
    total       = len(advice_list)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(metric_card("Total Activities", str(total)), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card("✅ Automatable", str(auto_count),
                                f"{auto_count/max(total,1):.0%} of steps", accent=True),
                    unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card("⚠️ Review First", str(review_count),
                                "pilot before full rollout"),
                    unsafe_allow_html=True)
    with c4:
        st.markdown(metric_card("🔴 Bottleneck", str(bot_count),
                                "address upstream causes"),
                    unsafe_allow_html=True)

    # Legend
    st.markdown("""
<div style="display:flex;gap:1rem;margin:1rem 0 1.5rem;flex-wrap:wrap;">
  <span style="font-size:0.8rem;color:var(--gray);">
    <strong>Legend:</strong>
    &nbsp;✅ Automatable — consistent, rule-following steps
    &nbsp;·&nbsp; ⚠️ Review — needs piloting or human oversight
    &nbsp;·&nbsp; 🔴 Bottleneck — high-variance, tackle upstream root cause
  </span>
</div>
""", unsafe_allow_html=True)

    # Filter
    status_filter = st.radio(
        "Show:",
        ["All", "✅ Automatable", "⚠️ Review", "🔴 Bottleneck"],
        horizontal=True,
        key="guide_filter",
    )
    filter_map = {
        "All":             None,
        "✅ Automatable":  "automatable",
        "⚠️ Review":       "review",
        "🔴 Bottleneck":   "bottleneck",
    }
    selected_status = filter_map[status_filter]

    shown = 0
    for adv in advice_list:
        if selected_status and adv.status != selected_status:
            continue
        st.markdown(_advice_card(adv), unsafe_allow_html=True)
        shown += 1

    if shown == 0:
        st.info("No activities match this filter.")

    # Download guide as CSV
    guide_rows = [
        {
            "Activity": a.activity,
            "Status": a.status_label,
            "Reason": a.reason,
            "How to Automate": a.how_to_automate,
            "Tools": ", ".join(a.tools_suggested),
            "Estimated Saving %": f"{int(a.estimated_saving_pct*100)}%",
            "Source": a.source,
        }
        for a in advice_list
    ]
    guide_df = pd.DataFrame(guide_rows)
    st.download_button(
        "⬇️  Download Automation Guide (CSV)",
        data=guide_df.to_csv(index=False).encode(),
        file_name="automation_guide.csv",
        mime="text/csv",
        key="dl_guide",
    )


# ── Tab 3: Gate Demo ─────────────────────────────────────────────────────────

def render_gate_demo_tab(gate_results: list[dict[str, Any]]) -> None:
    st.markdown(section_header("Gate Engine — Live Decisions"), unsafe_allow_html=True)
    st.markdown(
        "<p style='color:var(--gray);font-size:0.875rem;margin-bottom:1rem;'>"
        "Each scenario sends a case through the LLM → Gate Engine pipeline. "
        "Use buttons in the sidebar to run scenarios.</p>",
        unsafe_allow_html=True,
    )

    if not gate_results:
        st.info("Run a scenario (▶ A / B / C) from the sidebar to see gate decisions.", icon="💡")
        # Show architecture explanation
        st.markdown("""
<div style="background:var(--stone-50);border-radius:var(--radius-xl);padding:1.25rem 1.5rem;
            border:1px solid var(--stone-100);margin-top:1rem;">
<strong>How it works:</strong>
<ol style="color:var(--night);font-size:0.875rem;margin-top:0.5rem;">
  <li><strong>Context</strong> — a case arrives at an automatable step</li>
  <li><strong>LLM proposes</strong> — Groq/deterministic agent suggests an action + confidence score</li>
  <li><strong>Gate evaluates</strong> — checks confidence ≥ 0.80, action in allowlist, not high-impact</li>
  <li><strong>Decision</strong> — APPROVED / DENIED / ESCALATED logged to audit trail</li>
</ol>
<p style="font-size:0.8rem;color:var(--gray);margin-top:0.5rem;">
  ⚠️ The LLM <strong>never executes anything</strong>. It only proposes. The gate decides.
</p>
</div>
""", unsafe_allow_html=True)
        return

    for result in reversed(gate_results):   # newest first
        decision = result["decision"]
        proposal = result["proposal"]
        context  = result["context"]

        bg_map = {"APPROVED":"#d1fae5","DENIED":"#fee2e2","ESCALATED":"#fef3c7"}
        bg = bg_map.get(decision, _STONE_50)

        with st.expander(
            f"Scenario {result['scenario']} — "
            f"{status_badge(decision)} — `{proposal['action']}`",
            expanded=True,
        ):
            c1, c2, c3 = st.columns(3)
            with c1: st.metric("Action",      proposal["action"])
            with c2: st.metric("Confidence",  f"{proposal['confidence']:.0%}")
            with c3: st.metric("Decision",    decision)

            st.markdown(
                f"**Case:** `{context.get('case_id')}` | "
                f"**Step:** `{context.get('activity')}` | "
                f"**Amount:** ${context.get('amount', 0):,.2f}"
            )
            st.markdown(f"_LLM reasoning:_ {proposal['reasoning']}")
            st.markdown(
                f'<div style="background:{bg};border-radius:var(--radius-lg);'
                f'padding:0.75rem 1rem;border-left:3px solid var(--grape);margin-top:0.5rem;">'
                f"<strong>Gate reason:</strong> {result['reason']}</div>",
                unsafe_allow_html=True,
            )


# ── Tab 4: Metrics & ROI ─────────────────────────────────────────────────────

def render_metrics_tab(process_map: ProcessMap) -> None:
    st.markdown(section_header("ROI & Impact Metrics"), unsafe_allow_html=True)
    stats       = process_map.activity_stats
    total_cases = sum(process_map.variant_counts.values())
    auto_steps  = process_map.automatable_steps

    time_saved_per_case = sum(
        stats[s].mean_seconds for s in auto_steps if s in stats
    )
    auto_frac = (
        (process_map.variant_counts.get("happy_path", 0)
         + process_map.variant_counts.get("escalation", 0))
        / max(total_cases, 1)
    )
    automated_cases   = int(total_cases * auto_frac)
    before_avg_days   = sum(s.mean_seconds for s in stats.values()) / 86_400
    saved_days        = time_saved_per_case / 86_400
    after_avg_days    = max(before_avg_days - saved_days, 0)
    manual_mins       = len(auto_steps) * 2
    hourly_rate       = 30
    roi               = (manual_mins / 60) * hourly_rate * automated_cases

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(metric_card("Total Cases", f"{total_cases:,}"), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card("Cases Automatable", f"{automated_cases:,}",
                                f"{auto_frac:.0%} of volume", accent=True),
                    unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card("Avg Cycle Time (Before)", f"{before_avg_days:.1f}d"),
                    unsafe_allow_html=True)
    with c4:
        st.markdown(metric_card("Avg Cycle Time (After)", f"{after_avg_days:.1f}d",
                                f"−{saved_days:.1f}d per case", accent=True),
                    unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    c5, c6 = st.columns(2)
    with c5:
        st.markdown(
            metric_card("Est. Labour Saving", f"£{roi:,.0f}",
                        f"@ £{hourly_rate}/hr · {manual_mins} min/case", accent=True),
            unsafe_allow_html=True,
        )
    with c6:
        st.markdown(
            metric_card("Automatable Steps", str(len(auto_steps)),
                        ", ".join(auto_steps) or "none"),
            unsafe_allow_html=True,
        )

    st.markdown(section_header("Variant Breakdown"), unsafe_allow_html=True)
    variant_df = pd.DataFrame([
        {"Variant": v, "Cases": c, "Share": f"{c/max(total_cases,1):.0%}"}
        for v, c in sorted(process_map.variant_counts.items(), key=lambda x: -x[1])
    ])
    st.dataframe(variant_df, width="stretch", hide_index=True)
    st.caption(
        "⚠️ Metrics are derived from the uploaded data. ROI uses £30/hr and "
        "2 min/activity — adjust for your context. See README for full limitations."
    )


# ── Main entrypoint ──────────────────────────────────────────────────────────

def render_dashboard(
    process_map: ProcessMap,
    gate_results: list[dict[str, Any]],
    advice_list: list[ActivityAdvice],
) -> None:
    tab1, tab2, tab3, tab4 = st.tabs([
        "🗺️  Process Map",
        "✅  Automation Guide",
        "⚡  Gate Demo",
        "📊  Metrics & ROI",
    ])
    with tab1: render_process_map_tab(process_map)
    with tab2: render_automation_guide_tab(advice_list)
    with tab3: render_gate_demo_tab(gate_results)
    with tab4: render_metrics_tab(process_map)

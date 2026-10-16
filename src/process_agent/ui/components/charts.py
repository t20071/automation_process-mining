"""
src/process_agent/ui/components/charts.py

Chart builders.  Pure functions: data in, chart spec out.

- build_dot()          Directly-Follows Graph as a Graphviz DOT string.
                       st.graphviz_chart renders DOT client-side, so no native
                       Graphviz binary is needed on Streamlit Community Cloud.
- *_chart()            Altair (Vega-Lite) charts, themed by config.toml.
"""

from __future__ import annotations

import html

import altair as alt
import pandas as pd

from process_agent.mining.analytics import fmt_duration
from process_agent.mining.process_mining import ProcessMap
from process_agent.ui.components.theme import GRAY, NIGHT, STATUS, STONE_50, STONE_100

_SERIES = STATUS["review"]["color"]   # single-series colour


# ---------------------------------------------------------------------------
# Process map (DOT)
# ---------------------------------------------------------------------------


def _q(name: str) -> str:
    """Quote a node id for DOT."""
    return '"' + str(name).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _node(activity: str, pm: ProcessMap, status: str | None) -> str:
    s = pm.activity_stats.get(activity)
    meta = STATUS.get(status or "", None)
    fill, border = (meta["tint"], meta["color"]) if meta else (STONE_50, STONE_100)
    sub = f"{s.count:,}× · avg {fmt_duration(s.mean_seconds)}" if s else ""
    title = html.escape(activity.replace("_", " "))
    label = (
        f'<<font point-size="17"><b>{title}</b></font><br/>'
        f'<font point-size="13" color="{GRAY}">{html.escape(sub)}</font>>'
    )
    return (
        f"{_q(activity)} [label={label}, fillcolor=\"{fill}\", "
        f"color=\"{border}\", penwidth=1.6];"
    )


def _edge(src: str, tgt: str, freq: int, wait: float, max_freq: int, metric: str) -> str:
    ratio = freq / max(max_freq, 1)
    width = 0.8 + 4.2 * ratio
    shade = int(170 - 120 * ratio)          # darker = more frequent
    color = f"#{shade:02x}{shade:02x}{min(shade + 20, 255):02x}"
    label = f"{freq:,}" if metric == "frequency" else fmt_duration(wait)
    return (
        f"{_q(src)} -> {_q(tgt)} [penwidth={width:.2f}, color=\"{color}\", "
        f"label=\" {label} \", fontcolor=\"{NIGHT}\"];"
    )


def build_dot(
    pm: ProcessMap,
    status_by_activity: dict[str, str],
    metric: str = "frequency",
    min_share: float = 0.0,
) -> str:
    """
    Render the DFG as DOT.

    metric     : "frequency" (case transitions) or "time" (mean wait) edge labels
    min_share  : hide transitions used by fewer than this share of the busiest
                 transition (0–1), to declutter spaghetti processes
    """
    max_freq = max((e.frequency for e in pm.dfg_edges), default=1)
    edges = [e for e in pm.dfg_edges if e.frequency >= min_share * max_freq]
    shown = {e.source for e in edges} | {e.target for e in edges}
    shown |= set(pm.start_activities) | set(pm.end_activities)

    lines = [
        "digraph G {",
        'rankdir=LR; bgcolor="transparent"; nodesep=0.35; ranksep=0.55; pad=0.2;',
        'node [shape=box, style="rounded,filled", fontname="Inter", margin="0.22,0.1"];',
        'edge [fontname="Inter", fontsize=14, arrowsize=0.8];',
        f'"__start__" [shape=circle, label="", width=0.22, style=filled, fillcolor="{NIGHT}", color="{NIGHT}"];',
        f'"__end__" [shape=doublecircle, label="", width=0.18, style=filled, fillcolor="{NIGHT}", color="{NIGHT}"];',
    ]
    lines += [_node(a, pm, status_by_activity.get(a)) for a in sorted(shown)]
    lines += [
        _edge(e.source, e.target, e.frequency, e.mean_duration, max_freq, metric)
        for e in edges
    ]
    for act, n in pm.start_activities.items():
        if act in shown:
            lines.append(f'"__start__" -> {_q(act)} [style=dashed, color="{GRAY}", label=" {n:,} ", fontcolor="{GRAY}"];')
    for act, n in pm.end_activities.items():
        if act in shown:
            lines.append(f'{_q(act)} -> "__end__" [style=dashed, color="{GRAY}", label=" {n:,} ", fontcolor="{GRAY}"];')
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Altair charts
# ---------------------------------------------------------------------------


def _status_scale() -> alt.Scale:
    return alt.Scale(
        domain=[m["label"] for m in STATUS.values()],
        range=[m["color"] for m in STATUS.values()],
    )


def activity_duration_chart(rows: pd.DataFrame) -> alt.LayerChart:
    """
    Horizontal bars of mean duration (hours) per activity, coloured by status,
    with a tick at P95.  ``rows`` needs: activity, mean_hours, p95_hours,
    count, status_label.
    """
    order = rows.sort_values("mean_hours", ascending=False)["activity"].tolist()
    y = alt.Y("activity:N", sort=order, title=None, axis=alt.Axis(labelLimit=180))
    tooltip = [
        alt.Tooltip("activity:N", title="Activity"),
        alt.Tooltip("status_label:N", title="Status"),
        alt.Tooltip("mean_hours:Q", title="Mean (h)", format=",.1f"),
        alt.Tooltip("p95_hours:Q", title="P95 (h)", format=",.1f"),
        alt.Tooltip("count:Q", title="Executions", format=","),
    ]
    bars = alt.Chart(rows).mark_bar(cornerRadiusEnd=4, height=16).encode(
        x=alt.X("mean_hours:Q", title="Mean duration (hours)"),
        y=y,
        color=alt.Color("status_label:N", scale=_status_scale(), title=None,
                        legend=alt.Legend(orient="top")),
        tooltip=tooltip,
    )
    ticks = alt.Chart(rows).mark_tick(color=NIGHT, thickness=2, size=18, opacity=0.55).encode(
        x="p95_hours:Q", y=y, tooltip=tooltip,
    )
    return (bars + ticks).properties(height=max(36 * len(rows), 160))


def throughput_histogram(cases: pd.DataFrame) -> alt.Chart:
    """Distribution of end-to-end case throughput (days)."""
    return (
        alt.Chart(cases)
        .mark_bar(color=_SERIES, cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("throughput_days:Q", bin=alt.Bin(maxbins=40), title="Throughput (days)"),
            y=alt.Y("count():Q", title="Cases"),
            tooltip=[
                alt.Tooltip("throughput_days:Q", bin=alt.Bin(maxbins=40), title="Days"),
                alt.Tooltip("count():Q", title="Cases", format=","),
            ],
        )
        .properties(height=240)
    )


def weekly_volume_chart(trend: pd.DataFrame) -> alt.Chart:
    """Cases started per week."""
    return (
        alt.Chart(trend)
        .mark_bar(color=_SERIES, cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("week:T", title=None),
            y=alt.Y("cases:Q", title="Cases started"),
            tooltip=[alt.Tooltip("week:T", title="Week of"),
                     alt.Tooltip("cases:Q", title="Cases", format=",")],
        )
        .properties(height=220)
    )


def weekly_throughput_chart(trend: pd.DataFrame) -> alt.LayerChart:
    """Median throughput per start week (single series, crosshair-friendly)."""
    base = alt.Chart(trend).encode(x=alt.X("week:T", title=None))
    line = base.mark_line(color=_SERIES, strokeWidth=2).encode(
        y=alt.Y("median_days:Q", title="Median throughput (days)",
                scale=alt.Scale(zero=False)),
    )
    hover = alt.selection_point(fields=["week"], nearest=True, on="pointerover", empty=False)
    points = base.mark_point(color=_SERIES, filled=True, size=70).encode(
        y="median_days:Q",
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("week:T", title="Week of"),
                 alt.Tooltip("median_days:Q", title="Median days", format=".2f"),
                 alt.Tooltip("cases:Q", title="Cases", format=",")],
    ).add_params(hover)
    return (line + points).properties(height=220)


def savings_chart(rows: pd.DataFrame, value_col: str, title: str) -> alt.Chart:
    """Horizontal bars of a saving metric per activity, coloured by status."""
    order = rows.sort_values(value_col, ascending=False)["activity"].tolist()
    present = [m for m in STATUS.values() if m["label"] in set(rows["status_label"])]
    scale = alt.Scale(domain=[m["label"] for m in present], range=[m["color"] for m in present])
    return (
        alt.Chart(rows)
        .mark_bar(cornerRadiusEnd=4, height=16)
        .encode(
            x=alt.X(f"{value_col}:Q", title=title),
            y=alt.Y("activity:N", sort=order, title=None, axis=alt.Axis(labelLimit=180)),
            color=alt.Color("status_label:N", scale=scale, title=None,
                            legend=alt.Legend(orient="top")),
            tooltip=[alt.Tooltip("activity:N", title="Activity"),
                     alt.Tooltip(f"{value_col}:Q", title=title, format=",.1f")],
        )
        .properties(height=max(36 * len(rows), 140))
    )

"""
src/process_agent/mining/process_mining.py

Lightweight Directly-Follows Graph (DFG) discovery using pandas + networkx.
No pm4py dependency — hand-rolled groupby approach for reliable deployment.

Public API
----------
discover_process_map(df) -> ProcessMap
    Mine the DFG, compute per-activity cycle-time stats, flag bottlenecks,
    and identify automatable step candidates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import networkx as nx
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ActivityStats:
    """Cycle-time statistics for a single activity."""

    activity: str
    mean_seconds: float
    std_seconds: float
    p95_seconds: float
    count: int
    is_bottleneck: bool = False
    is_automatable: bool = False


@dataclass
class DFGEdge:
    """A directed Directly-Follows edge."""

    source: str
    target: str
    frequency: int          # how many times this transition occurred
    mean_duration: float    # mean time between source start and target start


@dataclass
class ProcessMap:
    """Full output of the process mining step."""

    graph: nx.DiGraph
    activity_stats: dict[str, ActivityStats]
    dfg_edges: list[DFGEdge]
    bottlenecks: list[str]          # top-N high-variance activities
    automatable_steps: list[str]    # low-variance, consistent steps
    variant_counts: dict[str, int]  # case count per variant


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_BOTTLENECK_TOP_N = 3
_AUTOMATABLE_CV_THRESHOLD = 0.30   # coefficient of variation ≤ 30 % → automatable
_AUTOMATABLE_MIN_COUNT = 10        # must have enough observations


def _compute_activity_stats(df: pd.DataFrame) -> dict[str, ActivityStats]:
    """Compute mean, std, P95 cycle time per activity."""
    grouped = df.groupby("activity")["duration_seconds"]
    stats: dict[str, ActivityStats] = {}
    for activity, durations in grouped:
        mean = float(durations.mean())
        std = float(durations.std(ddof=1)) if len(durations) > 1 else 0.0
        p95 = float(durations.quantile(0.95))
        stats[activity] = ActivityStats(
            activity=str(activity),
            mean_seconds=mean,
            std_seconds=std,
            p95_seconds=p95,
            count=int(len(durations)),
        )
    return stats


def _flag_bottlenecks(
    stats: dict[str, ActivityStats],
    top_n: int = _BOTTLENECK_TOP_N,
) -> list[str]:
    """
    Flag the top-N activities by std_seconds as bottlenecks.
    Updates stats in-place; returns list of bottleneck activity names.
    """
    sorted_acts = sorted(
        stats.values(), key=lambda s: s.std_seconds, reverse=True
    )
    bottlenecks = [s.activity for s in sorted_acts[:top_n]]
    for act in bottlenecks:
        stats[act].is_bottleneck = True
    return bottlenecks


def _flag_automatable(
    stats: dict[str, ActivityStats],
    cv_threshold: float = _AUTOMATABLE_CV_THRESHOLD,
    min_count: int = _AUTOMATABLE_MIN_COUNT,
) -> list[str]:
    """
    Flag activities with coefficient of variation ≤ cv_threshold as
    automatable (consistent, predictable durations).
    Updates stats in-place; returns list of automatable activity names.
    """
    automatable: list[str] = []
    for act_stats in stats.values():
        if act_stats.count < min_count:
            continue
        if act_stats.mean_seconds == 0:
            continue
        cv = act_stats.std_seconds / act_stats.mean_seconds
        if cv <= cv_threshold:
            act_stats.is_automatable = True
            automatable.append(act_stats.activity)
    return automatable


def _build_dfg(df: pd.DataFrame) -> tuple[nx.DiGraph, list[DFGEdge]]:
    """
    Build a Directly-Follows Graph from the event log.

    For each case, pair consecutive activities (sorted by timestamp).
    Count transitions and compute mean inter-event duration.
    """
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df.sort_values(["case_id", "timestamp"], inplace=True)

    # Shift to get the next activity within the same case
    grp = df.groupby("case_id", group_keys=False)

    next_activity = grp["activity"].shift(-1)
    next_timestamp = grp["timestamp"].shift(-1)

    transitions = df.copy()
    transitions["next_activity"] = next_activity
    transitions["next_timestamp"] = next_timestamp
    transitions["wait_seconds"] = (
        transitions["next_timestamp"] - transitions["timestamp"]
    ).dt.total_seconds()

    # Drop the last event of each case (no next activity)
    transitions = transitions.dropna(subset=["next_activity"])

    # Aggregate
    edge_stats = (
        transitions.groupby(["activity", "next_activity"])
        .agg(frequency=("case_id", "count"), mean_duration=("wait_seconds", "mean"))
        .reset_index()
    )

    G = nx.DiGraph()
    edges: list[DFGEdge] = []

    for _, row in edge_stats.iterrows():
        src = str(row["activity"])
        tgt = str(row["next_activity"])
        freq = int(row["frequency"])
        mean_dur = float(row["mean_duration"])
        G.add_edge(src, tgt, frequency=freq, mean_duration=mean_dur)
        edges.append(
            DFGEdge(
                source=src, target=tgt, frequency=freq, mean_duration=mean_dur
            )
        )

    logger.info(
        "Built DFG",
        extra={"nodes": G.number_of_nodes(), "edges": G.number_of_edges()},
    )
    return G, edges


def _count_variants(df: pd.DataFrame) -> dict[str, int]:
    """Return case count per variant."""
    case_df = df.drop_duplicates(subset="case_id")
    return case_df["variant"].value_counts().to_dict()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def discover_process_map(df: pd.DataFrame) -> ProcessMap:
    """
    Mine the process map from an event-log DataFrame.

    Parameters
    ----------
    df : DataFrame with columns case_id, activity, timestamp,
         duration_seconds, variant.

    Returns
    -------
    ProcessMap with DFG, activity stats, bottlenecks, automatable steps.
    """
    _validate_df(df)

    activity_stats = _compute_activity_stats(df)
    bottlenecks = _flag_bottlenecks(activity_stats)
    automatable_steps = _flag_automatable(activity_stats)
    graph, dfg_edges = _build_dfg(df)
    variant_counts = _count_variants(df)

    logger.info(
        "Process map discovered",
        extra={
            "bottlenecks": bottlenecks,
            "automatable_steps": automatable_steps,
            "variants": list(variant_counts.keys()),
        },
    )

    return ProcessMap(
        graph=graph,
        activity_stats=activity_stats,
        dfg_edges=dfg_edges,
        bottlenecks=bottlenecks,
        automatable_steps=automatable_steps,
        variant_counts=variant_counts,
    )


def _validate_df(df: pd.DataFrame) -> None:
    required = {"case_id", "activity", "timestamp", "duration_seconds"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Event log is missing required columns: {missing}")
    if df.empty:
        raise ValueError("Event log DataFrame is empty.")


def cycle_time_summary(process_map: ProcessMap) -> pd.DataFrame:
    """
    Return a tidy DataFrame of per-activity cycle-time stats, sorted by
    std_seconds descending (bottlenecks first).
    """
    rows = [
        {
            "activity": s.activity,
            "mean_seconds": round(s.mean_seconds, 1),
            "std_seconds": round(s.std_seconds, 1),
            "p95_seconds": round(s.p95_seconds, 1),
            "count": s.count,
            "is_bottleneck": s.is_bottleneck,
            "is_automatable": s.is_automatable,
        }
        for s in process_map.activity_stats.values()
    ]
    return (
        pd.DataFrame(rows)
        .sort_values("std_seconds", ascending=False)
        .reset_index(drop=True)
    )

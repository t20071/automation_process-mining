"""
src/process_agent/mining/analytics.py

Case-level analytics layered on top of the event log and ProcessMap:

- case_table()      one row per case: path, throughput, rework, exception flags
- path_summary()    process "variants" by actual activity sequence
- weekly_trend()    case volume and median throughput per start week
- health_score()    0–100 composite of conformance, rework and predictability
- generate_insights()  deterministic, data-grounded key findings
- estimate_roi()    labour and cycle-time impact of automating flagged steps

Everything here is deterministic and side-effect free so it is cheap to cache
and easy to unit test.  No LLM is involved in producing these numbers.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from process_agent.mining.process_mining import ProcessMap

DAY = 86_400.0
_REWORK_KEYWORDS = ("reject", "resubmit", "rework", "redo", "correct", "return")
_EXCEPTION_KEYWORDS = ("hold", "missing", "exception", "pending", "dispute", "error")


def fmt_duration(seconds: float) -> str:
    """Human-friendly duration: 45s, 12m, 3.4h, 2.1d."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3_600:
        return f"{seconds / 60:.0f}m"
    if seconds < DAY:
        return f"{seconds / 3_600:.1f}h"
    return f"{seconds / DAY:.1f}d"


def _keyword_flag(activities: pd.Series, keywords: tuple[str, ...]) -> pd.Series:
    return activities.str.lower().str.contains("|".join(keywords), regex=True)


# ---------------------------------------------------------------------------
# Case table
# ---------------------------------------------------------------------------


def case_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per case with path, throughput and quality flags."""
    ev = df.assign(
        timestamp=pd.to_datetime(df["timestamp"], utc=True),
        activity=df["activity"].astype(str),
    ).sort_values(["case_id", "timestamp"])
    ev["_repeat"] = ev.duplicated(["case_id", "activity"])
    ev["_rework"] = ev["_repeat"] | _keyword_flag(ev["activity"], _REWORK_KEYWORDS)
    ev["_exception"] = _keyword_flag(ev["activity"], _EXCEPTION_KEYWORDS)
    g = ev.groupby("case_id", sort=False)

    last = g.last()
    end = last["timestamp"] + pd.to_timedelta(last["duration_seconds"], unit="s")
    cases = pd.DataFrame({
        "variant": g["variant"].first() if "variant" in ev else "unknown",
        "path": g["activity"].agg(" → ".join),
        "start": g["timestamp"].first(),
        "n_events": g.size(),
        "has_rework": g["_rework"].any(),
        "has_exception": g["_exception"].any(),
        "amount": g["amount"].first().astype(float) if "amount" in ev else 0.0,
    })
    cases["throughput_seconds"] = (end - cases["start"]).dt.total_seconds().clip(lower=0)
    cases["throughput_days"] = cases["throughput_seconds"] / DAY
    return cases.rename_axis("case_id").reset_index()


def path_summary(cases: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Most frequent activity sequences with share and throughput."""
    total = max(len(cases), 1)
    summary = (
        cases.groupby("path")
        .agg(
            cases=("case_id", "count"),
            median_days=("throughput_days", "median"),
            p90_days=("throughput_days", lambda s: s.quantile(0.9)),
            steps=("n_events", "median"),
        )
        .sort_values("cases", ascending=False)
        .head(top_n)
        .reset_index()
    )
    summary["share"] = summary["cases"] / total
    return summary


def weekly_trend(cases: pd.DataFrame) -> pd.DataFrame:
    """Cases started and median throughput (days) per calendar week."""
    week = cases["start"].dt.tz_localize(None).dt.to_period("W").dt.start_time
    trend = (
        cases.assign(week=week)
        .groupby("week")
        .agg(cases=("case_id", "count"), median_days=("throughput_days", "median"))
        .reset_index()
    )
    return trend


# ---------------------------------------------------------------------------
# Health score
# ---------------------------------------------------------------------------


@dataclass
class HealthScore:
    score: int                 # 0–100
    conformance: float         # share of cases on the dominant path
    rework_free: float         # share of cases without rework
    predictability: float      # 1 − weighted mean coefficient of variation
    label: str                 # "Healthy" | "Fair" | "At risk"


def _predictability(process_map: ProcessMap) -> float:
    stats = [s for s in process_map.activity_stats.values() if s.mean_seconds > 0]
    total = sum(s.count for s in stats)
    if not total:
        return 1.0
    weighted_cv = sum(s.std_seconds / s.mean_seconds * s.count for s in stats) / total
    return max(0.0, 1.0 - min(weighted_cv, 1.0))


def health_score(cases: pd.DataFrame, process_map: ProcessMap) -> HealthScore:
    """Composite 0–100: 40% conformance, 30% rework-free, 30% predictability."""
    n = max(len(cases), 1)
    conformance = float(cases["path"].value_counts().iloc[0] / n) if len(cases) else 0.0
    rework_free = 1.0 - float(cases["has_rework"].mean()) if len(cases) else 1.0
    predictability = _predictability(process_map)
    score = round(100 * (0.4 * conformance + 0.3 * rework_free + 0.3 * predictability))
    label = "Healthy" if score >= 80 else "Fair" if score >= 60 else "At risk"
    return HealthScore(score, conformance, rework_free, predictability, label)


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------


@dataclass
class Insight:
    icon: str        # Material Symbols name, e.g. "hourglass_top"
    title: str
    detail: str
    tone: str        # "risk" | "opportunity" | "info"


def _time_sink_insight(pm: ProcessMap) -> Insight | None:
    totals = {a: s.mean_seconds * s.count for a, s in pm.activity_stats.items()}
    grand = sum(totals.values())
    if not grand:
        return None
    act = max(totals, key=totals.get)
    s = pm.activity_stats[act]
    return Insight(
        "hourglass_top",
        f"`{act}` consumes {totals[act] / grand:.0%} of all process time",
        f"It runs {s.count:,} times averaging {fmt_duration(s.mean_seconds)} "
        f"(P95 {fmt_duration(s.p95_seconds)}). Shortening it has the largest "
        "effect on end-to-end cycle time.",
        "risk",
    )


def _variability_insight(pm: ProcessMap) -> Insight | None:
    candidates = [s for s in pm.activity_stats.values() if s.mean_seconds > 0]
    if not candidates:
        return None
    s = max(candidates, key=lambda x: x.std_seconds)
    spread = s.p95_seconds / s.mean_seconds
    return Insight(
        "ssid_chart",
        f"`{s.activity}` is the least predictable step",
        f"Standard deviation of {fmt_duration(s.std_seconds)}; the slowest 5% of "
        f"cases take {spread:.1f}× the average. Variance like this usually points "
        "to queueing or missing information rather than effort.",
        "risk",
    )


def _path_gap_insight(cases: pd.DataFrame) -> Insight | None:
    paths = path_summary(cases, top_n=20)
    paths = paths[paths["cases"] >= max(5, 0.02 * len(cases))]
    if len(paths) < 2:
        return None
    fast = paths.loc[paths["median_days"].idxmin()]
    slow = paths.loc[paths["median_days"].idxmax()]
    if fast["median_days"] <= 0:
        return None
    ratio = slow["median_days"] / fast["median_days"]
    return Insight(
        "alt_route",
        f"The slowest common path takes {ratio:.1f}× longer than the fastest",
        f"{slow['share']:.0%} of cases follow `{slow['path']}` "
        f"(median {slow['median_days']:.1f}d) versus `{fast['path']}` "
        f"(median {fast['median_days']:.1f}d).",
        "info",
    )


def _rework_insight(cases: pd.DataFrame) -> Insight | None:
    rate = float(cases["has_rework"].mean())
    if rate == 0:
        return None
    with_rw = cases.loc[cases["has_rework"], "throughput_days"].median()
    without = cases.loc[~cases["has_rework"], "throughput_days"].median()
    extra = (
        f" Those cases take a median {with_rw - without:.1f}d longer."
        if pd.notna(without) and with_rw > without
        else ""
    )
    return Insight(
        "replay",
        f"{rate:.0%} of cases loop back for rework",
        f"{int(cases['has_rework'].sum()):,} cases repeat a step or are rejected and "
        f"resubmitted.{extra} Validating inputs at submission prevents most loops.",
        "risk",
    )


def _automation_insight(
    cases: pd.DataFrame, df: pd.DataFrame, automatable: list[str]
) -> Insight | None:
    if not automatable:
        return None
    touched = df.loc[df["activity"].isin(automatable), "case_id"].nunique()
    share = touched / max(len(cases), 1)
    steps = ", ".join(f"`{s}`" for s in automatable)
    noun = "step is" if len(automatable) == 1 else "steps are"
    return Insight(
        "bolt",
        f"{len(automatable)} consistent {noun} ready to automate",
        f"{steps} run with low variance and appear in {share:.0%} of cases — "
        "strong candidates for rule-based or agent-assisted automation behind "
        "the decision gate.",
        "opportunity",
    )


def _value_insight(cases: pd.DataFrame) -> Insight | None:
    if cases["amount"].nunique() < 10:
        return None
    cutoff = cases["amount"].quantile(0.75)
    high = cases.loc[cases["amount"] >= cutoff, "throughput_days"].median()
    rest = cases.loc[cases["amount"] < cutoff, "throughput_days"].median()
    if pd.isna(high) or pd.isna(rest) or not rest or abs(high - rest) / rest < 0.10:
        return None
    direction = "slower" if high > rest else "faster"
    return Insight(
        "payments",
        f"High-value cases move {abs(high / rest - 1):.0%} {direction}",
        f"Cases in the top amount quartile (≥ {cutoff:,.0f}) take a median "
        f"{high:.1f}d versus {rest:.1f}d for the rest.",
        "info",
    )


def generate_insights(
    df: pd.DataFrame,
    cases: pd.DataFrame,
    pm: ProcessMap,
    automatable: list[str] | None = None,
) -> list[Insight]:
    """
    Deterministic, data-grounded findings ordered by importance.

    ``automatable`` defaults to the statistically consistent steps; pass the
    advisor's classification to account for human-judgment steps.
    """
    steps = pm.automatable_steps if automatable is None else automatable
    builders = [
        lambda: _time_sink_insight(pm),
        lambda: _rework_insight(cases),
        lambda: _automation_insight(cases, df, steps),
        lambda: _variability_insight(pm),
        lambda: _path_gap_insight(cases),
        lambda: _value_insight(cases),
    ]
    return [i for i in (b() for b in builders) if i is not None]


# ---------------------------------------------------------------------------
# ROI
# ---------------------------------------------------------------------------


@dataclass
class RoiEstimate:
    automated_executions: int
    hours_saved: float
    labour_saving: float
    cases_touched: int
    cases_touched_pct: float
    before_mean_days: float
    after_mean_days: float
    span_days: float
    annual_factor: float      # multiply log-period figures by this to annualise


def estimate_roi(
    df: pd.DataFrame,
    cases: pd.DataFrame,
    saving_pct: dict[str, float],
    hourly_rate: float = 30.0,
    minutes_per_step: float = 2.0,
    adoption: float = 1.0,
) -> RoiEstimate:
    """
    Estimate impact of automating the activities in ``saving_pct``.

    - Labour: each automated execution frees ``minutes_per_step`` of handling.
    - Cycle time: each automated event's duration shrinks by its saving %.
    Both scale with ``adoption`` (share of executions actually automated).
    """
    auto = df[df["activity"].isin(saving_pct.keys())]
    executions = int(round(len(auto) * adoption))
    hours = executions * minutes_per_step / 60
    cut = (auto["duration_seconds"] * auto["activity"].map(saving_pct)).groupby(
        auto["case_id"]
    ).sum() * adoption
    after = (
        cases["throughput_seconds"] - cut.reindex(cases["case_id"]).fillna(0).values
    ).clip(lower=0)
    ts = pd.to_datetime(df["timestamp"], utc=True)
    span = max((ts.max() - ts.min()).total_seconds() / DAY, 1.0)
    touched = int(auto["case_id"].nunique())
    return RoiEstimate(
        automated_executions=executions,
        hours_saved=hours,
        labour_saving=hours * hourly_rate,
        cases_touched=touched,
        cases_touched_pct=touched / max(len(cases), 1),
        before_mean_days=float(cases["throughput_days"].mean()) if len(cases) else 0.0,
        after_mean_days=float(after.mean() / DAY) if len(after) else 0.0,
        span_days=span,
        annual_factor=365.0 / span,
    )

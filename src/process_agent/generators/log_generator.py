"""
src/process_agent/generators/log_generator.py

Generates ~2,000 synthetic expense-reimbursement event logs across four
process variants.  Output: data/event_logs.csv.

Variants
--------
happy_path       (50%) submit → manager_approval → finance_approval → paid
escalation       (20%) submit → manager_approval → finance_review → paid
rejection_loop   (20%) submit → manager_rejects → resubmit → manager_approval → paid
exception        (10%) submit → missing_receipt → hold → resolved → paid
"""

from __future__ import annotations

import logging
import os
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

VARIANTS: dict[str, float] = {
    "happy_path": 0.50,
    "escalation": 0.20,
    "rejection_loop": 0.20,
    "exception": 0.10,
}

# Mean duration (seconds) and std-dev per activity
_ACTIVITY_STATS: dict[str, tuple[float, float]] = {
    "submit": (300, 60),
    "manager_approval": (86_400, 21_600),  # ~1 day ± 6 h
    "finance_approval": (43_200, 7_200),   # ~12 h ± 2 h
    "finance_review": (172_800, 43_200),   # ~2 days ± 12 h  ← bottleneck
    "manager_rejects": (3_600, 600),
    "resubmit": (7_200, 1_800),
    "paid": (3_600, 900),
    "missing_receipt": (1_800, 300),
    "hold": (259_200, 86_400),             # ~3 days ± 1 day ← bottleneck
    "resolved": (3_600, 600),
}

# Activities we consider automatable (low std-dev relative to mean)
AUTOMATABLE_ACTIVITIES: frozenset[str] = frozenset(
    {"submit", "missing_receipt", "resolved", "paid"}
)


@dataclass
class EventRow:
    case_id: str
    activity: str
    timestamp: datetime
    duration_seconds: float
    variant: str
    amount: float
    submitter_id: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _pick_variant(rng: random.Random) -> str:
    population = list(VARIANTS.keys())
    weights = list(VARIANTS.values())
    return rng.choices(population, weights=weights, k=1)[0]


def _activity_duration(activity: str, rng: random.Random) -> float:
    """Return a non-negative duration (seconds) sampled from a normal dist."""
    mean, std = _ACTIVITY_STATS.get(activity, (600, 120))
    duration = rng.gauss(mean, std)
    return max(duration, 30.0)  # floor at 30 s


def _activities_for_variant(variant: str) -> list[str]:
    """Return the ordered activity sequence for a given variant."""
    sequences: dict[str, list[str]] = {
        "happy_path": [
            "submit", "manager_approval", "finance_approval", "paid"
        ],
        "escalation": [
            "submit", "manager_approval", "finance_review", "paid"
        ],
        "rejection_loop": [
            "submit", "manager_rejects", "resubmit", "manager_approval", "paid"
        ],
        "exception": [
            "submit", "missing_receipt", "hold", "resolved", "paid"
        ],
    }
    return sequences[variant]


def _generate_case(
    case_index: int,
    rng: random.Random,
    start_window: datetime,
) -> Iterator[EventRow]:
    """Yield all event rows for a single case."""
    variant = _pick_variant(rng)
    case_id = f"CASE-{case_index:05d}"
    amount = round(rng.uniform(50.0, 5_000.0), 2)
    submitter_id = f"EMP-{rng.randint(1, 200):03d}"

    # Spread case start times across the start_window ± 90 days
    offset_days = rng.uniform(-90, 90)
    current_ts = start_window + timedelta(days=offset_days)

    for activity in _activities_for_variant(variant):
        duration = _activity_duration(activity, rng)
        yield EventRow(
            case_id=case_id,
            activity=activity,
            timestamp=current_ts,
            duration_seconds=round(duration, 2),
            variant=variant,
            amount=amount,
            submitter_id=submitter_id,
        )
        current_ts += timedelta(seconds=duration)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_event_log(
    num_cases: int = 2_000,
    seed: int = 42,
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    """
    Generate synthetic event log with *num_cases* cases.

    Parameters
    ----------
    num_cases:    Number of cases to generate.
    seed:         Random seed for reproducibility.
    output_path:  If provided, write CSV to this path (creates parent dirs).

    Returns
    -------
    DataFrame with columns:
        case_id, activity, timestamp, duration_seconds, variant, amount,
        submitter_id
    """
    rng = random.Random(seed)
    start_window = datetime(2024, 1, 1, tzinfo=timezone.utc)

    rows: list[dict] = []
    for i in range(1, num_cases + 1):
        for event in _generate_case(i, rng, start_window):
            rows.append(
                {
                    "case_id": event.case_id,
                    "activity": event.activity,
                    "timestamp": event.timestamp.isoformat(),
                    "duration_seconds": event.duration_seconds,
                    "variant": event.variant,
                    "amount": event.amount,
                    "submitter_id": event.submitter_id,
                }
            )

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df.sort_values(["case_id", "timestamp"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    logger.info(
        "Generated event log",
        extra={"num_cases": num_cases, "num_events": len(df)},
    )

    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
        logger.info("Wrote event log", extra={"path": str(path)})

    return df


def load_or_generate(
    output_path: str | Path = "data/event_logs.csv",
    num_cases: int = 2_000,
    seed: int = 42,
    force_regenerate: bool = False,
) -> pd.DataFrame:
    """
    Load CSV if it exists, otherwise generate and save it.

    Parameters
    ----------
    output_path:      Path to the CSV file.
    num_cases:        Number of cases to generate if file is missing.
    seed:             RNG seed.
    force_regenerate: Always regenerate even if file exists.
    """
    path = Path(output_path)
    if path.exists() and not force_regenerate:
        logger.info("Loading existing event log", extra={"path": str(path)})
        df = pd.read_csv(path, parse_dates=["timestamp"])
        return df
    return generate_event_log(
        num_cases=num_cases, seed=seed, output_path=output_path
    )


if __name__ == "__main__":
    from process_agent.logging_config import setup_logging

    setup_logging()
    df = generate_event_log(num_cases=2_000, output_path="data/event_logs.csv")
    print(f"Generated {len(df)} events across {df['case_id'].nunique()} cases.")
    print(df["variant"].value_counts(normalize=True).round(3))

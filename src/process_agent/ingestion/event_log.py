"""
src/process_agent/ingestion/event_log.py

Event-log ingestion: auto-detect column names, validate, and normalise an
uploaded CSV into the canonical schema used by the mining modules.

Canonical schema
----------------
Required : case_id, activity, timestamp, duration_seconds
Optional : variant, amount, submitter_id

If ``duration_seconds`` is missing but timestamps are present, each event's
duration is derived as the time until the next event in the same case
(the final event of a case gets 0 s).  This lets plain
case/activity/timestamp logs — the most common export format — work as-is.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ("case_id", "activity", "timestamp", "duration_seconds")
OPTIONAL_DEFAULTS: dict[str, object] = {
    "variant": "unknown",
    "amount": 0.0,
    "submitter_id": "unknown",
}

# Aliases for auto-detection (compared after normalisation)
ALIASES: dict[str, list[str]] = {
    "case_id": ["caseid", "case", "id", "ticketid", "claimid", "incidentid",
                "caseconceptname", "traceid"],
    "activity": ["activity", "activities", "task", "step", "event", "action",
                 "activityname", "conceptname"],
    "timestamp": ["timestamp", "time", "datetime", "starttime", "startedat",
                  "date", "timetimestamp", "eventtime"],
    "duration_seconds": ["durationseconds", "duration", "durationinseconds",
                         "timetaken", "elapsed", "elapsedseconds"],
    "variant": ["variant", "path", "processpath", "processvariant", "flow"],
    "amount": ["amount", "value", "cost", "price", "total", "claimamount"],
    "submitter_id": ["submitterid", "submitter", "user", "userid", "employeeid",
                     "empid", "resource", "orgresource"],
}


@dataclass
class IngestResult:
    """Outcome of ingesting a raw event-log DataFrame."""

    df: pd.DataFrame | None
    mapping: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.df is not None and not self.errors


def _normalise(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def map_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """Rename recognised columns to canonical names; return (df, mapping)."""
    by_norm = {_normalise(c): c for c in df.columns}
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for standard, aliases in ALIASES.items():
        candidates = [standard, *aliases]
        for alias in candidates:
            source = by_norm.get(_normalise(alias))
            if source is not None and source not in used:
                mapping[source] = standard
                used.add(source)
                break
    renamed = df.rename(columns={k: v for k, v in mapping.items() if k != v})
    return renamed, mapping


def _derive_durations(df: pd.DataFrame) -> pd.Series:
    """Seconds until the next event in the same case (0 for the last event)."""
    ordered = df.sort_values(["case_id", "timestamp"])
    nxt = ordered.groupby("case_id")["timestamp"].shift(-1)
    secs = (nxt - ordered["timestamp"]).dt.total_seconds().fillna(0.0)
    return secs.clip(lower=0.0).reindex(df.index)


def _validate(df: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if df.empty:
        return ["The file has no rows."]
    missing = [c for c in ("case_id", "activity", "timestamp") if c not in df.columns]
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}")
    return errors


def normalise_event_log(raw: pd.DataFrame) -> IngestResult:
    """Map, validate and clean a raw event log into the canonical schema."""
    df, mapping = map_columns(raw)
    errors = _validate(df)
    if errors:
        return IngestResult(df=None, mapping=mapping, errors=errors)

    notes: list[str] = []
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    bad_ts = int(df["timestamp"].isna().sum())
    if bad_ts == len(df):
        return IngestResult(None, mapping, ["Column `timestamp` could not be parsed."])
    if bad_ts:
        df = df.dropna(subset=["timestamp"])
        notes.append(f"Dropped {bad_ts:,} rows with unparseable timestamps.")

    df["case_id"] = df["case_id"].astype(str)
    df["activity"] = df["activity"].astype(str).str.strip()

    if "duration_seconds" in df.columns:
        df["duration_seconds"] = pd.to_numeric(df["duration_seconds"], errors="coerce")
        if df["duration_seconds"].isna().all():
            return IngestResult(None, mapping, ["Column `duration_seconds` must be numeric."])
        df["duration_seconds"] = df["duration_seconds"].fillna(0.0).clip(lower=0.0)
    else:
        df["duration_seconds"] = _derive_durations(df)
        notes.append("No duration column found — derived durations from timestamps.")

    for col, default in OPTIONAL_DEFAULTS.items():
        if col not in df.columns:
            df[col] = default

    df = df.sort_values(["case_id", "timestamp"]).reset_index(drop=True)
    logger.info("Ingested event log", extra={"rows": len(df), "notes": notes})
    return IngestResult(df=df, mapping=mapping, notes=notes)

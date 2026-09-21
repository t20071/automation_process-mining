"""
src/process_agent/config.py

Single source of truth for all application settings.
Reads secrets via st.secrets (deployed) with os.environ fallback (local dev).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum


class LLMProvider(str, Enum):
    """Supported LLM provider backends."""

    GROQ = "groq"
    DETERMINISTIC = "deterministic"


def _get_api_key() -> str:
    """
    Read the Groq API key without ever hardcoding it.
    Priority:
      1. st.secrets["GROQ_API_KEY"]  (Streamlit Cloud)
      2. os.environ["GROQ_API_KEY"]   (local dev / CI)
    """
    try:
        import streamlit as st  # type: ignore[import]

        return st.secrets["GROQ_API_KEY"]
    except Exception:
        return os.environ.get("GROQ_API_KEY", "")


def _load_env() -> None:
    """Load .env for local development (no-op when already set)."""
    try:
        from dotenv import load_dotenv

        load_dotenv(override=False)
    except ImportError:
        pass


@dataclass
class Settings:
    """All application settings — read once at startup."""

    llm_provider: LLMProvider = field(
        default_factory=lambda: LLMProvider(
            os.environ.get("LLM_PROVIDER", LLMProvider.DETERMINISTIC)
        )
    )
    groq_api_key: str = field(default_factory=_get_api_key)
    groq_model: str = "llama3-8b-8192"

    # Gate engine thresholds
    confidence_threshold: float = float(
        os.environ.get("CONFIDENCE_THRESHOLD", "0.80")
    )

    # Policy: only these actions may be auto-approved
    policy_allowlist: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "check_receipt_completeness",
                "validate_expense_category",
                "flag_duplicate_submission",
            }
        )
    )

    # Actions that require extra scrutiny regardless of confidence
    high_impact_actions: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "approve_payment",
                "reject_claim",
                "escalate_to_finance",
            }
        )
    )

    # Log generator
    num_cases: int = int(os.environ.get("NUM_CASES", "2000"))

    # Paths (relative to project root)
    event_log_path: str = "data/event_logs.csv"
    audit_log_path: str = "audit/decisions_log.jsonl"


def get_settings() -> Settings:
    """Return a fully initialised Settings object."""
    _load_env()          # populate os.environ from .env first
    return Settings()    # then dataclass lambdas read the populated env

"""
src/process_agent/config.py

Single source of truth for all application settings.
Reads secrets via st.secrets (deployed) with os.environ fallback (local dev).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


class LLMProvider(str, Enum):
    """Supported LLM provider backends."""

    GROQ = "groq"
    DETERMINISTIC = "deterministic"


def _get_secret(name: str, default: str = "") -> str:
    """
    Read a setting without ever hardcoding it.
    Priority:
      1. st.secrets[name]  (Streamlit Cloud)
      2. os.environ[name]  (local dev / CI)
    """
    try:
        import streamlit as st  # type: ignore[import]

        value = st.secrets.get(name)
        if value not in (None, ""):
            return str(value)
    except Exception:
        pass
    return os.environ.get(name, default)


def _get_api_key() -> str:
    return _get_secret("GROQ_API_KEY")


def _get_provider() -> LLMProvider:
    """Explicit LLM_PROVIDER wins; otherwise use Groq only when a key exists."""
    explicit = _get_secret("LLM_PROVIDER").strip().lower()
    if explicit in {p.value for p in LLMProvider}:
        return LLMProvider(explicit)
    return LLMProvider.GROQ if _get_api_key() else LLMProvider.DETERMINISTIC


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

    llm_provider: LLMProvider = field(default_factory=_get_provider)
    groq_api_key: str = field(default_factory=_get_api_key)
    groq_model: str = field(
        default_factory=lambda: _get_secret("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    )

    # Gate engine thresholds
    confidence_threshold: float = field(
        default_factory=lambda: float(_get_secret("CONFIDENCE_THRESHOLD", "0.80"))
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
    num_cases: int = field(
        default_factory=lambda: int(_get_secret("NUM_CASES", "2000"))
    )

    # Paths (relative to project root)
    event_log_path: str = "data/event_logs.csv"
    audit_log_path: str = "audit/decisions_log.jsonl"

    @property
    def live_llm(self) -> bool:
        """True when the Groq provider is selected and a key is available."""
        return self.llm_provider == LLMProvider.GROQ and bool(self.groq_api_key)


def get_settings() -> Settings:
    """Return a fully initialised Settings object."""
    _load_env()          # populate os.environ from .env first
    return Settings()    # then dataclass factories read the populated env

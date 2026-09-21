"""
src/process_agent/agent/llm_client.py

LLM client layer.  The agent emits structured ActionProposal objects only —
it never executes anything directly.

Providers
---------
GroqLLMClient         — calls Groq API (OpenAI-compatible).  Used in live demos.
DeterministicLLMClient — returns canned responses.  Used in all tests / CI.

Usage
-----
    from process_agent.agent.llm_client import get_client, ActionProposal

    client = get_client(provider="deterministic")
    proposal = client.propose_action(context)
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model — the ONLY thing an agent may produce
# ---------------------------------------------------------------------------


@dataclass
class ActionProposal:
    """
    Schema-validated action proposal emitted by the LLM.

    The gate engine consumes this; nothing in the system executes an action
    without gate approval.
    """

    action: str                      # e.g. "check_receipt_completeness"
    confidence: float                # 0.0 – 1.0
    reasoning: str                   # brief rationale from the model
    affected_fields: list[str]       # which case fields this action touches
    raw_response: str = ""           # full LLM response string for audit

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be in [0, 1]; got {self.confidence}"
            )
        if not self.action:
            raise ValueError("action must be a non-empty string")


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class LLMClient(ABC):
    """Base class for all LLM provider backends."""

    @abstractmethod
    def propose_action(self, context: dict[str, Any]) -> ActionProposal:
        """
        Given a process context dict, return a single ActionProposal.

        Parameters
        ----------
        context : dict with at minimum:
            - case_id : str
            - activity : str  (the step to automate)
            - amount   : float
            - variant  : str
            (plus any domain-specific fields)
        """


# ---------------------------------------------------------------------------
# Deterministic client — for tests / CI (no network calls)
# ---------------------------------------------------------------------------

_CANNED: dict[str, dict[str, Any]] = {
    "scenario_a": {
        "action": "check_receipt_completeness",
        "confidence": 0.92,
        "reasoning": "All required fields present; receipt hash matches.",
        "affected_fields": ["receipt_status", "validation_flag"],
    },
    "scenario_b": {
        "action": "approve_payment",          # NOT in allowlist → DENIED
        "confidence": 0.95,
        "reasoning": "Payment criteria met per policy.",
        "affected_fields": ["payment_status"],
    },
    "scenario_c": {
        "action": "check_receipt_completeness",
        "confidence": 0.61,                   # below threshold → ESCALATED
        "reasoning": "Receipt image quality is poor; unable to verify totals.",
        "affected_fields": ["receipt_status"],
    },
}


class DeterministicLLMClient(LLMClient):
    """
    Returns canned ActionProposal objects for testing.
    The `scenario` key selects which canned response to return.
    """

    def __init__(self, scenario: str = "scenario_a") -> None:
        if scenario not in _CANNED:
            raise ValueError(
                f"Unknown scenario '{scenario}'. "
                f"Choose from: {list(_CANNED.keys())}"
            )
        self._scenario = scenario

    def propose_action(self, context: dict[str, Any]) -> ActionProposal:
        canned = _CANNED[self._scenario]
        raw = json.dumps(canned)
        logger.info(
            "DeterministicLLMClient proposal",
            extra={"scenario": self._scenario, "context_case": context.get("case_id")},
        )
        return ActionProposal(
            action=canned["action"],
            confidence=canned["confidence"],
            reasoning=canned["reasoning"],
            affected_fields=list(canned["affected_fields"]),
            raw_response=raw,
        )


# ---------------------------------------------------------------------------
# Groq client — for live demos (requires GROQ_API_KEY)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a process automation assistant.
Given a business process case, propose exactly ONE automation action as JSON.

Your response MUST be valid JSON with these exact keys:
{
  "action": "<action_name>",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<brief explanation>",
  "affected_fields": ["<field1>", "<field2>"]
}

Rules:
- action must be a snake_case identifier
- confidence must reflect your genuine certainty
- reasoning must be ≤ 2 sentences
- Do not include any text outside the JSON object
"""


def _build_user_prompt(context: dict[str, Any]) -> str:
    return (
        "Process case context:\n"
        + json.dumps(context, indent=2, default=str)
        + "\n\nPropose an automation action for the current step."
    )


def _parse_proposal(raw: str, context: dict[str, Any]) -> ActionProposal:
    """Parse JSON response from Groq into an ActionProposal."""
    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse LLM response as JSON", extra={"raw": raw})
        raise ValueError(f"LLM returned non-JSON response: {exc}") from exc

    return ActionProposal(
        action=str(data.get("action", "")),
        confidence=float(data.get("confidence", 0.0)),
        reasoning=str(data.get("reasoning", "")),
        affected_fields=list(data.get("affected_fields", [])),
        raw_response=raw,
    )


class GroqLLMClient(LLMClient):
    """Calls the Groq API (OpenAI-compatible endpoint)."""

    def __init__(self, api_key: str, model: str = "llama3-8b-8192") -> None:
        try:
            from groq import Groq  # type: ignore[import]
        except ImportError as exc:
            raise ImportError("Install 'groq' package: pip install groq") from exc

        self._client = Groq(api_key=api_key)  # type: ignore[name-defined]
        self._model = model

    def propose_action(self, context: dict[str, Any]) -> ActionProposal:
        user_prompt = _build_user_prompt(context)
        logger.info(
            "Calling Groq API",
            extra={"model": self._model, "case_id": context.get("case_id")},
        )
        completion = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=256,
        )
        raw = completion.choices[0].message.content or ""
        return _parse_proposal(raw, context)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_client(
    provider: str = "deterministic",
    api_key: str = "",
    model: str = "llama3-8b-8192",
    scenario: str = "scenario_a",
) -> LLMClient:
    """
    Return the appropriate LLMClient for the given provider string.

    Parameters
    ----------
    provider  : "groq" or "deterministic"
    api_key   : Required when provider="groq"
    model     : Groq model name
    scenario  : Canned scenario for DeterministicLLMClient
    """
    if provider == "groq":
        if not api_key:
            raise ValueError(
                "api_key is required for the Groq provider. "
                "Set GROQ_API_KEY in .env or st.secrets."
            )
        return GroqLLMClient(api_key=api_key, model=model)
    if provider == "deterministic":
        return DeterministicLLMClient(scenario=scenario)
    raise ValueError(
        f"Unknown provider '{provider}'. Choose 'groq' or 'deterministic'."
    )

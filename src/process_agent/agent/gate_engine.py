"""
src/process_agent/agent/gate_engine.py

Deterministic gate engine.  Evaluates every ActionProposal against:
  1. Confidence gate      — reject/escalate if confidence < threshold
  2. Policy allowlist     — deny if action not in approved set
  3. High-impact gate     — escalate if action is high-impact

Every decision (APPROVED / DENIED / ESCALATED) is appended to the audit log
at audit/decisions_log.jsonl — no silent decisions.

CRITICAL: This module never executes any action.  It only decides whether
the proposal *may* proceed and records that decision.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from process_agent.agent.llm_client import ActionProposal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Decision model
# ---------------------------------------------------------------------------


class GateDecision(str, Enum):
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    ESCALATED = "ESCALATED"


@dataclass
class GateResult:
    """Full output of the gate engine evaluation."""

    decision: GateDecision
    reason: str
    proposal: ActionProposal
    context: dict[str, Any]
    evaluated_at: str = ""   # ISO-8601 UTC timestamp, set in __post_init__

    def __post_init__(self) -> None:
        if not self.evaluated_at:
            self.evaluated_at = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Gate engine
# ---------------------------------------------------------------------------


class GateEngine:
    """
    Deterministic evaluator for ActionProposals.

    Parameters
    ----------
    confidence_threshold : Proposals below this confidence are escalated.
    policy_allowlist     : Only actions in this set may be approved.
    high_impact_actions  : Actions that trigger extra scrutiny → escalation.
    audit_log_path       : Path to the append-only JSONL decision log.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.80,
        policy_allowlist: frozenset[str] | None = None,
        high_impact_actions: frozenset[str] | None = None,
        audit_log_path: str | Path = "audit/decisions_log.jsonl",
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.policy_allowlist: frozenset[str] = policy_allowlist or frozenset(
            {
                "check_receipt_completeness",
                "validate_expense_category",
                "flag_duplicate_submission",
            }
        )
        self.high_impact_actions: frozenset[str] = high_impact_actions or frozenset(
            {
                "approve_payment",
                "reject_claim",
                "escalate_to_finance",
            }
        )
        self.audit_log_path = Path(audit_log_path)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def evaluate(
        self, proposal: ActionProposal, context: dict[str, Any]
    ) -> GateResult:
        """
        Evaluate an ActionProposal and return a GateResult.

        Gates are applied in order:
          1. Confidence    → ESCALATED if too low
          2. Policy        → DENIED if action not allowlisted
          3. High-impact   → ESCALATED if action is high-impact

        If all gates pass → APPROVED.
        """
        result = (
            self._check_confidence(proposal, context)
            or self._check_policy(proposal, context)
            or self._check_high_impact(proposal, context)
            or self._approve(proposal, context)
        )
        self._append_audit_log(result)
        return result

    # ------------------------------------------------------------------ #
    # Individual gate checks (each returns GateResult or None)
    # ------------------------------------------------------------------ #

    def _check_confidence(
        self, proposal: ActionProposal, context: dict[str, Any]
    ) -> GateResult | None:
        if proposal.confidence < self.confidence_threshold:
            return GateResult(
                decision=GateDecision.ESCALATED,
                reason=(
                    f"Confidence {proposal.confidence:.2f} is below "
                    f"threshold {self.confidence_threshold:.2f}. "
                    "Routed to human review queue."
                ),
                proposal=proposal,
                context=context,
            )
        return None

    def _check_policy(
        self, proposal: ActionProposal, context: dict[str, Any]
    ) -> GateResult | None:
        if proposal.action not in self.policy_allowlist:
            return GateResult(
                decision=GateDecision.DENIED,
                reason=(
                    f"Action '{proposal.action}' is not in the policy allowlist. "
                    f"Allowed actions: {sorted(self.policy_allowlist)}."
                ),
                proposal=proposal,
                context=context,
            )
        return None

    def _check_high_impact(
        self, proposal: ActionProposal, context: dict[str, Any]
    ) -> GateResult | None:
        if proposal.action in self.high_impact_actions:
            return GateResult(
                decision=GateDecision.ESCALATED,
                reason=(
                    f"Action '{proposal.action}' is classified as high-impact "
                    "and requires human approval."
                ),
                proposal=proposal,
                context=context,
            )
        return None

    def _approve(
        self, proposal: ActionProposal, context: dict[str, Any]
    ) -> GateResult:
        return GateResult(
            decision=GateDecision.APPROVED,
            reason=(
                f"All gates passed. Confidence {proposal.confidence:.2f} ≥ "
                f"{self.confidence_threshold:.2f}. "
                f"Action '{proposal.action}' is allowlisted and not high-impact."
            ),
            proposal=proposal,
            context=context,
        )

    # ------------------------------------------------------------------ #
    # Audit logging — append-only, never overwrites
    # ------------------------------------------------------------------ #

    def _append_audit_log(self, result: GateResult) -> None:
        """Append the gate decision to the JSONL audit log."""
        try:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "evaluated_at": result.evaluated_at,
                "decision": result.decision.value,
                "reason": result.reason,
                "proposal": {
                    "action": result.proposal.action,
                    "confidence": result.proposal.confidence,
                    "reasoning": result.proposal.reasoning,
                    "affected_fields": result.proposal.affected_fields,
                },
                "context": result.context,
            }
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            logger.info(
                "Gate decision logged",
                extra={
                    "decision": result.decision.value,
                    "action": result.proposal.action,
                    "case_id": result.context.get("case_id"),
                },
            )
        except OSError as exc:
            logger.error(
                "Failed to write audit log",
                extra={"error": str(exc), "path": str(self.audit_log_path)},
            )

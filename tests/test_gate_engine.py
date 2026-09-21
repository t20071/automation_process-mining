"""
tests/test_gate_engine.py

Unit tests for the deterministic gate engine.
All tests use DeterministicLLMClient — zero live API calls.

Scenario A: high confidence + allowlisted action   → APPROVED
Scenario B: policy violation (action not in list)  → DENIED
Scenario C: low confidence                         → ESCALATED
"""

from __future__ import annotations

from pathlib import Path

import pytest

from process_agent.agent.gate_engine import GateDecision, GateEngine, GateResult
from process_agent.agent.llm_client import ActionProposal, DeterministicLLMClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CONTEXT = {
    "case_id": "CASE-00001",
    "activity": "check_receipt_completeness",
    "amount": 350.00,
    "variant": "happy_path",
    "submitter_id": "EMP-042",
}


def _engine(tmp_path: Path) -> GateEngine:
    """GateEngine that writes audit log to a temp directory."""
    return GateEngine(
        confidence_threshold=0.80,
        policy_allowlist=frozenset(
            {
                "check_receipt_completeness",
                "validate_expense_category",
                "flag_duplicate_submission",
            }
        ),
        high_impact_actions=frozenset(
            {"approve_payment", "reject_claim", "escalate_to_finance"}
        ),
        audit_log_path=tmp_path / "audit" / "decisions_log.jsonl",
    )


# ---------------------------------------------------------------------------
# Scenario A — clean auto-approval
# ---------------------------------------------------------------------------


class TestScenarioA:
    """High confidence + allowlisted action → APPROVED."""

    def test_decision_is_approved(self, tmp_path: Path) -> None:
        client = DeterministicLLMClient(scenario="scenario_a")
        proposal = client.propose_action(SAMPLE_CONTEXT)
        result = _engine(tmp_path).evaluate(proposal, SAMPLE_CONTEXT)
        assert result.decision == GateDecision.APPROVED

    def test_approved_reason_mentions_gates(self, tmp_path: Path) -> None:
        client = DeterministicLLMClient(scenario="scenario_a")
        proposal = client.propose_action(SAMPLE_CONTEXT)
        result = _engine(tmp_path).evaluate(proposal, SAMPLE_CONTEXT)
        assert "All gates passed" in result.reason

    def test_approved_proposal_preserved(self, tmp_path: Path) -> None:
        client = DeterministicLLMClient(scenario="scenario_a")
        proposal = client.propose_action(SAMPLE_CONTEXT)
        result = _engine(tmp_path).evaluate(proposal, SAMPLE_CONTEXT)
        assert result.proposal.action == "check_receipt_completeness"
        assert result.proposal.confidence == pytest.approx(0.92)

    def test_audit_log_written(self, tmp_path: Path) -> None:
        client = DeterministicLLMClient(scenario="scenario_a")
        proposal = client.propose_action(SAMPLE_CONTEXT)
        engine = _engine(tmp_path)
        engine.evaluate(proposal, SAMPLE_CONTEXT)
        assert engine.audit_log_path.exists()

    def test_audit_log_contains_decision(self, tmp_path: Path) -> None:
        import json

        client = DeterministicLLMClient(scenario="scenario_a")
        proposal = client.propose_action(SAMPLE_CONTEXT)
        engine = _engine(tmp_path)
        engine.evaluate(proposal, SAMPLE_CONTEXT)
        lines = engine.audit_log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["decision"] == "APPROVED"
        assert "proposal" in entry
        assert "context" in entry


# ---------------------------------------------------------------------------
# Scenario B — policy gate denies
# ---------------------------------------------------------------------------


class TestScenarioB:
    """Action not in allowlist → DENIED."""

    def test_decision_is_denied(self, tmp_path: Path) -> None:
        client = DeterministicLLMClient(scenario="scenario_b")
        proposal = client.propose_action(SAMPLE_CONTEXT)
        result = _engine(tmp_path).evaluate(proposal, SAMPLE_CONTEXT)
        assert result.decision == GateDecision.DENIED

    def test_denied_reason_mentions_allowlist(self, tmp_path: Path) -> None:
        client = DeterministicLLMClient(scenario="scenario_b")
        proposal = client.propose_action(SAMPLE_CONTEXT)
        result = _engine(tmp_path).evaluate(proposal, SAMPLE_CONTEXT)
        assert "allowlist" in result.reason.lower()

    def test_denied_reason_mentions_action_name(self, tmp_path: Path) -> None:
        client = DeterministicLLMClient(scenario="scenario_b")
        proposal = client.propose_action(SAMPLE_CONTEXT)
        result = _engine(tmp_path).evaluate(proposal, SAMPLE_CONTEXT)
        assert proposal.action in result.reason

    def test_audit_log_has_denied_entry(self, tmp_path: Path) -> None:
        import json

        client = DeterministicLLMClient(scenario="scenario_b")
        proposal = client.propose_action(SAMPLE_CONTEXT)
        engine = _engine(tmp_path)
        engine.evaluate(proposal, SAMPLE_CONTEXT)
        lines = engine.audit_log_path.read_text().strip().splitlines()
        entry = json.loads(lines[0])
        assert entry["decision"] == "DENIED"


# ---------------------------------------------------------------------------
# Scenario C — low confidence → escalation
# ---------------------------------------------------------------------------


class TestScenarioC:
    """Confidence below threshold → ESCALATED."""

    def test_decision_is_escalated(self, tmp_path: Path) -> None:
        client = DeterministicLLMClient(scenario="scenario_c")
        proposal = client.propose_action(SAMPLE_CONTEXT)
        result = _engine(tmp_path).evaluate(proposal, SAMPLE_CONTEXT)
        assert result.decision == GateDecision.ESCALATED

    def test_escalated_reason_mentions_confidence(self, tmp_path: Path) -> None:
        client = DeterministicLLMClient(scenario="scenario_c")
        proposal = client.propose_action(SAMPLE_CONTEXT)
        result = _engine(tmp_path).evaluate(proposal, SAMPLE_CONTEXT)
        assert "confidence" in result.reason.lower()

    def test_escalated_reason_mentions_human_review(self, tmp_path: Path) -> None:
        client = DeterministicLLMClient(scenario="scenario_c")
        proposal = client.propose_action(SAMPLE_CONTEXT)
        result = _engine(tmp_path).evaluate(proposal, SAMPLE_CONTEXT)
        assert "human" in result.reason.lower()

    def test_audit_log_has_escalated_entry(self, tmp_path: Path) -> None:
        import json

        client = DeterministicLLMClient(scenario="scenario_c")
        proposal = client.propose_action(SAMPLE_CONTEXT)
        engine = _engine(tmp_path)
        engine.evaluate(proposal, SAMPLE_CONTEXT)
        lines = engine.audit_log_path.read_text().strip().splitlines()
        entry = json.loads(lines[0])
        assert entry["decision"] == "ESCALATED"


# ---------------------------------------------------------------------------
# Audit log append — multiple decisions
# ---------------------------------------------------------------------------


class TestAuditLog:
    def test_multiple_decisions_all_logged(self, tmp_path: Path) -> None:
        import json

        engine = _engine(tmp_path)
        for scenario in ("scenario_a", "scenario_b", "scenario_c"):
            client = DeterministicLLMClient(scenario=scenario)
            proposal = client.propose_action(SAMPLE_CONTEXT)
            engine.evaluate(proposal, SAMPLE_CONTEXT)

        lines = engine.audit_log_path.read_text().strip().splitlines()
        assert len(lines) == 3
        decisions = {json.loads(l)["decision"] for l in lines}
        assert decisions == {"APPROVED", "DENIED", "ESCALATED"}

    def test_audit_log_entries_have_timestamp(self, tmp_path: Path) -> None:
        import json

        engine = _engine(tmp_path)
        client = DeterministicLLMClient(scenario="scenario_a")
        proposal = client.propose_action(SAMPLE_CONTEXT)
        engine.evaluate(proposal, SAMPLE_CONTEXT)
        entry = json.loads(engine.audit_log_path.read_text().strip())
        assert "evaluated_at" in entry


# ---------------------------------------------------------------------------
# ActionProposal validation
# ---------------------------------------------------------------------------


class TestActionProposalValidation:
    def test_invalid_confidence_raises(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            ActionProposal(
                action="check_receipt_completeness",
                confidence=1.5,
                reasoning="test",
                affected_fields=[],
            )

    def test_empty_action_raises(self) -> None:
        with pytest.raises(ValueError, match="action"):
            ActionProposal(
                action="",
                confidence=0.9,
                reasoning="test",
                affected_fields=[],
            )


# ---------------------------------------------------------------------------
# High-impact gate
# ---------------------------------------------------------------------------


class TestHighImpactGate:
    def test_allowlisted_high_impact_action_is_escalated(
        self, tmp_path: Path
    ) -> None:
        """
        An action that IS allowlisted but ALSO is high-impact should escalate.
        (Demonstrates defence-in-depth — add it to both sets for this test.)
        """
        engine = GateEngine(
            confidence_threshold=0.80,
            policy_allowlist=frozenset({"approve_payment"}),
            high_impact_actions=frozenset({"approve_payment"}),
            audit_log_path=tmp_path / "audit" / "decisions_log.jsonl",
        )
        proposal = ActionProposal(
            action="approve_payment",
            confidence=0.95,
            reasoning="Payment valid.",
            affected_fields=["payment_status"],
        )
        result = engine.evaluate(proposal, SAMPLE_CONTEXT)
        assert result.decision == GateDecision.ESCALATED

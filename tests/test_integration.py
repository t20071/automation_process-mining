"""
tests/test_integration.py

Integration test: full pipeline from log generation → process mining →
LLM proposal → gate evaluation.  All using in-memory / deterministic
providers — no file I/O, no live API calls.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from process_agent.agent.gate_engine import GateDecision, GateEngine
from process_agent.agent.llm_client import DeterministicLLMClient
from process_agent.generators.log_generator import generate_event_log
from process_agent.mining.process_mining import discover_process_map


def test_full_pipeline_scenario_a(tmp_path: Path) -> None:
    """
    Happy-path: generate logs → mine process → propose → gate approves.
    """
    df = generate_event_log(num_cases=100, seed=0)
    process_map = discover_process_map(df)

    # Pick the first automatable step as the automation target
    assert process_map.automatable_steps, "Expected at least one automatable step"
    target_step = process_map.automatable_steps[0]

    context = {
        "case_id": "CASE-00001",
        "activity": target_step,
        "amount": 250.00,
        "variant": "happy_path",
    }

    client = DeterministicLLMClient(scenario="scenario_a")
    proposal = client.propose_action(context)
    engine = GateEngine(audit_log_path=tmp_path / "audit" / "decisions.jsonl")
    result = engine.evaluate(proposal, context)

    assert result.decision == GateDecision.APPROVED
    assert engine.audit_log_path.exists()


def test_full_pipeline_scenario_b(tmp_path: Path) -> None:
    """
    Policy violation: gate denies even high-confidence out-of-allowlist action.
    """
    df = generate_event_log(num_cases=100, seed=1)
    process_map = discover_process_map(df)

    context = {
        "case_id": "CASE-00002",
        "activity": "manager_approval",
        "amount": 1_200.00,
        "variant": "escalation",
    }

    client = DeterministicLLMClient(scenario="scenario_b")
    proposal = client.propose_action(context)
    engine = GateEngine(audit_log_path=tmp_path / "audit" / "decisions.jsonl")
    result = engine.evaluate(proposal, context)

    assert result.decision == GateDecision.DENIED


def test_full_pipeline_scenario_c(tmp_path: Path) -> None:
    """
    Low confidence: gate escalates to human review.
    """
    df = generate_event_log(num_cases=100, seed=2)
    process_map = discover_process_map(df)

    context = {
        "case_id": "CASE-00003",
        "activity": "check_receipt_completeness",
        "amount": 4_800.00,
        "variant": "exception",
    }

    client = DeterministicLLMClient(scenario="scenario_c")
    proposal = client.propose_action(context)
    engine = GateEngine(audit_log_path=tmp_path / "audit" / "decisions.jsonl")
    result = engine.evaluate(proposal, context)

    assert result.decision == GateDecision.ESCALATED


def test_process_map_has_bottlenecks(tmp_path: Path) -> None:
    df = generate_event_log(num_cases=500, seed=42)
    process_map = discover_process_map(df)
    assert len(process_map.bottlenecks) == 3
    # Known bottlenecks from our synthetic data
    assert "hold" in process_map.bottlenecks or "finance_review" in process_map.bottlenecks


def test_audit_log_accumulates_all_three_scenarios(tmp_path: Path) -> None:
    """All three scenario decisions appear in one audit log."""
    import json

    engine = GateEngine(audit_log_path=tmp_path / "audit" / "decisions.jsonl")
    context = {"case_id": "TEST", "activity": "check_receipt_completeness", "amount": 100}

    for scenario in ("scenario_a", "scenario_b", "scenario_c"):
        client = DeterministicLLMClient(scenario=scenario)
        proposal = client.propose_action(context)
        engine.evaluate(proposal, context)

    lines = engine.audit_log_path.read_text().strip().splitlines()
    assert len(lines) == 3
    decisions = {json.loads(l)["decision"] for l in lines}
    assert decisions == {"APPROVED", "DENIED", "ESCALATED"}

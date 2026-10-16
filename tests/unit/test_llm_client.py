"""Unit tests for LLM response parsing (no network calls)."""

from __future__ import annotations

import pytest

from process_agent.agent.llm_client import _parse_proposal, extract_json


@pytest.mark.parametrize("raw", [
    '{"action": "x"}',
    '```json\n{"action": "x"}\n```',
    'Sure! Here you go: {"action": "x"} Hope that helps.',
])
def test_extract_json_tolerates_fences_and_prose(raw: str) -> None:
    assert extract_json(raw) == {"action": "x"}


def test_parse_proposal_clamps_confidence() -> None:
    proposal = _parse_proposal('{"action": "a", "confidence": 1.7}', {})
    assert proposal.confidence == 1.0


def test_parse_proposal_rejects_non_json() -> None:
    with pytest.raises(ValueError):
        _parse_proposal("no json here", {})

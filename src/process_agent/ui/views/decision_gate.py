"""
src/process_agent/ui/views/decision_gate.py

Decision-gate tab.  Three ways to send an ActionProposal through the
deterministic GateEngine:

1. Scripted scenarios A/B/C — deterministic provider, reproducible demo.
2. Proposal sandbox — the user composes a proposal by hand.
3. Live agent — Groq proposes an action for a real case (when configured).

The LLM never executes anything: every path ends in GateEngine.evaluate(),
which only records a decision in the audit log.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import pandas as pd
import streamlit as st

from process_agent.agent.gate_engine import GateEngine
from process_agent.agent.llm_client import ActionProposal, get_client
from process_agent.config import Settings
from process_agent.ui.components.theme import decision_badge, eyebrow, flow_strip

SCENARIOS: dict[str, dict[str, Any]] = {
    "A": {
        "title": "Clean auto-approval",
        "body": "High-confidence receipt check on a £350 claim. Every gate passes.",
        "expect": "APPROVED",
        "llm": "scenario_a",
        "context": {"case_id": "DEMO-A-001", "activity": "check_receipt_completeness",
                    "amount": 350.00, "variant": "happy_path", "submitter_id": "EMP-042"},
    },
    "B": {
        "title": "Policy gate denies",
        "body": "Agent tries to approve a £4,800 payment — not an allowlisted action.",
        "expect": "DENIED",
        "llm": "scenario_b",
        "context": {"case_id": "DEMO-B-001", "activity": "manager_approval",
                    "amount": 4_800.00, "variant": "escalation", "submitter_id": "EMP-107"},
    },
    "C": {
        "title": "Low confidence escalates",
        "body": "Blurry receipt: the agent is only 61% sure, so a human takes over.",
        "expect": "ESCALATED",
        "llm": "scenario_c",
        "context": {"case_id": "DEMO-C-001", "activity": "check_receipt_completeness",
                    "amount": 1_200.00, "variant": "exception", "submitter_id": "EMP-033"},
    },
}

_TRACE_ICON = {"pass": ":green[:material/check_circle:]",
               "fail": ":red[:material/cancel:]",
               "skipped": ":gray[:material/remove_circle_outline:]"}


@st.cache_resource
def _engine(threshold: float, allow: frozenset[str], high: frozenset[str], path: str) -> GateEngine:
    return GateEngine(threshold, allow, high, path)


def engine_for(settings: Settings) -> GateEngine:
    return _engine(settings.confidence_threshold, settings.policy_allowlist,
                   settings.high_impact_actions, settings.audit_log_path)


def _record(source: str, proposal: ActionProposal, context: dict, engine: GateEngine) -> None:
    """Evaluate through the gate and store the outcome for display."""
    trace = engine.trace(proposal)
    result = engine.evaluate(proposal, context)
    st.session_state.gate_results.append({
        "source": source,
        "decision": result.decision.value,
        "reason": result.reason,
        "evaluated_at": result.evaluated_at,
        "proposal": {k: v for k, v in asdict(proposal).items() if k != "raw_response"},
        "context": context,
        "trace": [asdict(c) for c in trace],
    })


def run_scenario(label: str, settings: Settings) -> None:
    """Scripted scenarios always use the deterministic provider for reliability."""
    spec = SCENARIOS[label]
    client = get_client(provider="deterministic", scenario=spec["llm"])
    context = dict(spec["context"])
    _record(f"Scenario {label}", client.propose_action(context), context, engine_for(settings))


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _pipeline() -> None:
    flow_strip([
        ("Agent proposes", "Schema-validated JSON action with a confidence score"),
        ("Confidence gate", "Below threshold → escalate to a human"),
        ("Policy gate", "Action not allowlisted → deny"),
        ("Impact gate", "High-impact action → escalate"),
        ("Decision logged", "Append-only audit trail, no silent decisions"),
    ])


def _scenario_cards(settings: Settings) -> None:
    for col, (label, spec) in zip(st.columns(3, gap="medium"), SCENARIOS.items()):
        with col.container(border=True, height="stretch"):
            st.markdown(f"**Scenario {label} · {spec['title']}**")
            st.caption(spec["body"])
            st.markdown(f"Expected: {decision_badge(spec['expect'])}")
            st.button("Run scenario", key=f"btn_{label}", icon=":material/play_arrow:",
                      on_click=run_scenario, args=(label, settings), width="stretch")


def _sandbox(settings: Settings, activities: list[str]) -> None:
    actions = sorted(settings.policy_allowlist | settings.high_impact_actions)
    with st.form("sandbox", border=False):
        c1, c2 = st.columns(2)
        action = c1.selectbox("Proposed action", actions, accept_new_options=True,
                              help="Type a new action name to test an unknown action.")
        step = c2.selectbox("At process step", activities)
        confidence = c1.slider("Agent confidence", 0.0, 1.0, 0.85, 0.01)
        amount = c2.number_input("Claim amount", min_value=0.0, value=750.0, step=50.0)
        reasoning = st.text_input("Agent reasoning", "Sandbox proposal for gate testing.")
        submitted = st.form_submit_button("Send to gate", icon=":material/send:", type="primary")
    if submitted and action:
        proposal = ActionProposal(action=str(action), confidence=float(confidence),
                                  reasoning=reasoning, affected_fields=[])
        context = {"case_id": "SANDBOX", "activity": step, "amount": amount}
        _record("Sandbox", proposal, context, engine_for(settings))


def _live_agent(settings: Settings, df: pd.DataFrame) -> None:
    if not settings.live_llm:
        st.caption(":material/key: Add `GROQ_API_KEY` to the app secrets to let a live "
                   "LLM propose actions for real cases. Scripted scenarios and the "
                   "sandbox work without it.")
        return
    cases = df["case_id"].drop_duplicates().head(500).tolist()
    c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
    case_id = c1.selectbox("Case", cases, key="live_case")
    if c2.button("Ask the agent", icon=":material/auto_awesome:", width="stretch"):
        events = df[df["case_id"] == case_id]
        last = events.iloc[-1]
        context = {"case_id": case_id, "activity": str(last["activity"]),
                   "amount": float(last.get("amount", 0.0)),
                   "variant": str(last.get("variant", "unknown")),
                   "history": events["activity"].astype(str).tolist()}
        try:
            with st.spinner(f"Asking {settings.groq_model}…"):
                client = get_client("groq", settings.groq_api_key, settings.groq_model)
                proposal = client.propose_action(context)
        except Exception as exc:
            st.error(f"The live agent failed: {exc}", icon=":material/error:")
            return
        _record("Live agent", proposal, context, engine_for(settings))


def _result_detail(result: dict[str, Any]) -> None:
    proposal = result["proposal"]
    with st.container(border=True):
        st.markdown(f"#### {result['source']} &nbsp; {decision_badge(result['decision'])}")
        with st.container(horizontal=True):
            st.metric("Proposed action", proposal["action"])
            st.metric("Confidence", f"{proposal['confidence']:.0%}")
            st.metric("Case", result["context"].get("case_id", "—"))
        for check in result["trace"]:
            note = " · *not evaluated*" if check["status"] == "skipped" else ""
            st.markdown(f"{_TRACE_ICON[check['status']]} **{check['name']}** — "
                        f"{check['detail']}{note}")
        st.caption(f"Agent reasoning: {proposal['reasoning'] or '—'}")
        st.caption(f"Gate verdict: {result['reason']}")


def _decision_log(results: list[dict[str, Any]]) -> None:
    log = pd.DataFrame([{
        "Time": r["evaluated_at"][11:19], "Source": r["source"], "Decision": r["decision"],
        "Action": r["proposal"]["action"], "Confidence": r["proposal"]["confidence"],
        "Case": r["context"].get("case_id"),
    } for r in reversed(results)])
    st.dataframe(log, hide_index=True, width="stretch", column_config={
        "Confidence": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
    })
    with st.container(horizontal=True):
        st.download_button("Download audit log (JSONL)", icon=":material/download:",
                           data="\n".join(json.dumps(r, default=str) for r in results),
                           file_name="gate_decisions.jsonl", mime="application/json")
        if st.button("Clear session log", icon=":material/delete_sweep:", type="tertiary"):
            st.session_state.gate_results = []
            st.rerun()


def render_gate_tab(settings: Settings, df: pd.DataFrame, activities: list[str]) -> None:
    st.subheader("Decision gate")
    st.caption("The agent can only *propose*. A deterministic engine decides, and every "
               "decision is written to an append-only audit log — the LLM never executes "
               f"anything. Confidence threshold: **{settings.confidence_threshold:.0%}**.")
    _pipeline()
    st.space("small")
    eyebrow("Scripted scenarios")
    _scenario_cards(settings)

    left, right = st.columns(2, gap="medium")
    with left.container(border=True):
        st.markdown("##### :material/tune: Proposal sandbox")
        _sandbox(settings, activities)
    with right.container(border=True):
        st.markdown("##### :material/auto_awesome: Live agent")
        _live_agent(settings, df)

    results = st.session_state.gate_results
    if not results:
        st.caption("Run a scenario or send a proposal to see the gate's step-by-step verdict.")
        return
    eyebrow("Latest decision")
    _result_detail(results[-1])
    eyebrow("Session decision log")
    _decision_log(results)

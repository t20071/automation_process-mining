# Process Intelligence + Agentic Automation Engine — Implementation Plan

## Overview

Build a demonstration system that:
1. **Mines** the actual as-executed version of a business process from synthetic event logs
2. **Identifies** repeatable/automatable steps using a Directly-Follows Graph (DFG)
3. **Automates** those steps via an LLM agent (Groq API) with a strict deterministic gate engine — the agent only *proposes* actions, never executes them directly

The demo process is **expense reimbursement approval** with four variants: happy path, escalation, rejection loop, and exception (missing receipt).

---

## Architecture Principles

> [!IMPORTANT]
> **Non-negotiable**: The LLM/agent never executes anything directly. It emits schema-validated JSON proposals only. The gate engine (deterministic) evaluates every proposal against confidence, policy, and risk gates. Low-confidence or high-impact proposals escalate to human review.

---

## Proposed Changes

### Phase 1 — Project Scaffold

#### [NEW] `process_agent_project/` (root directory)

All source files will live under `d:\project_for_learnig\16.skan.ai\process_agent_project\`.

---

#### [NEW] `.gitignore`
Excludes `.env`, `.streamlit/secrets.toml`, `__pycache__/`, `.pytest_cache/`, `*.pyc`, `data/`, `audit/`.

#### [NEW] `.env.example`
Documents all required environment variables (`GROQ_API_KEY`, `LLM_PROVIDER`, etc.) with no real values.

#### [NEW] `.env`
LOCAL ONLY — real secrets. Never committed.

---

### Phase 2 — Configuration & Infrastructure

#### [NEW] `pyproject.toml`
- Package metadata for `process_agent`
- Dependencies: `streamlit`, `pandas`, `networkx`, `groq`, `python-dotenv`, `pytest`, `ruff`, `black`
- Tool config: `[tool.ruff]`, `[tool.black]`, `[tool.pytest.ini_options]`

#### [NEW] `requirements.txt`
Pinned versions for Streamlit Cloud deployment (generated from `pyproject.toml`).

#### [NEW] `Makefile`
- `make setup` — create venv + install deps
- `make test` — run pytest
- `make run` — launch Streamlit
- `make lint` — run ruff

#### [NEW] `.streamlit/config.toml`
Theme tokens from `SKILL_webdesign.md`:
```toml
[theme]
primaryColor = "#9677ff"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#e7ebe5"
textColor = "#161714"
font = "sans serif"
```

#### [NEW] `src/process_agent/config.py`
- `Settings` dataclass — single source of truth for all config
- Reads `GROQ_API_KEY` via `st.secrets` (deployed) with `os.environ.get` fallback
- `LLM_PROVIDER` enum: `groq` | `deterministic`
- Confidence threshold (default 0.80), policy allowlist, high-impact action list

#### [NEW] `src/process_agent/logging_config.py`
Structured JSON logging setup used by every module.

---

### Phase 3 — Log Generator (Build Step 1)

#### [NEW] `src/process_agent/generators/log_generator.py`
Generates ~2,000 synthetic expense reimbursement cases across four variants:
- **Happy path** (50%): `submit → manager_approval → finance_approval → paid`
- **Escalation** (20%): `submit → manager_approval → finance_review → paid`
- **Rejection loop** (20%): `submit → manager_rejects → resubmit → manager_approval → paid`
- **Exception** (10%): `submit → missing_receipt → hold → resolved → paid`

Each event row: `case_id, activity, timestamp, duration_seconds, variant, amount, submitter_id`.

Output: `data/event_logs.csv`.

#### [NEW] `tests/test_log_generator.py`
- Tests event count, required columns, variant distribution within tolerance, monotonic timestamps per case.

---

### Phase 4 — Process Mining (Build Step 2)

#### [NEW] `src/process_agent/mining/process_mining.py`
- **DFG Discovery**: `pandas groupby` + `networkx` DiGraph — no pm4py
- **Cycle time** per activity (mean, std dev, P95)
- **Bottleneck flagging**: top 3 high-variance steps
- **Automatable steps**: activities where duration std dev is low (consistent, predictable)
- Returns structured result: `ProcessMap` dataclass with DFG edges, node stats, bottlenecks

#### [NEW] `tests/test_process_mining.py`
- Tests DFG edge discovery, cycle-time calculation, bottleneck flagging using synthetic fixtures (no file I/O needed).

---

### Phase 5 — Agent + Gate Engine (Build Step 3)

#### [NEW] `src/process_agent/agent/llm_client.py`
- `LLMClient` base class with `propose_action(context: dict) -> ActionProposal`
- `GroqLLMClient`: calls Groq API (OpenAI-compatible), parses JSON response into `ActionProposal`
- `DeterministicLLMClient`: returns canned responses — **used in all tests, no live network call**
- `ActionProposal` schema (Pydantic or dataclass): `action`, `confidence: float`, `reasoning`, `affected_fields`

#### [NEW] `src/process_agent/agent/gate_engine.py`
Deterministic evaluation of every `ActionProposal`:
1. **Confidence gate**: reject if `confidence < threshold` (default 0.80) → escalate
2. **Policy allowlist gate**: reject if action not in the approved action list
3. **High-impact gate**: additional scrutiny for high-dollar or multi-system actions → escalate

Decision outcomes: `APPROVED`, `DENIED`, `ESCALATED`.

Every decision → appended to `audit/decisions_log.jsonl` with full input + decision + reason.

#### [NEW] `tests/test_gate_engine.py`
Three scenarios:
- Scenario A: high confidence + allowlisted → `APPROVED`
- Scenario B: policy violation → `DENIED`
- Scenario C: low confidence → `ESCALATED`

All tests use `DeterministicLLMClient` — zero live API calls.

---

### Phase 6 — Streamlit App (Build Step 4)

#### [NEW] `src/process_agent/ui/theme.py`
Injects CSS token block from `SKILL_webdesign.md` via `st.markdown`. Colors, type scale, radius, motion tokens.

#### [NEW] `src/process_agent/ui/dashboard.py`
Dashboard rendering:
- **Process Map tab**: DFG visualization (networkx → matplotlib), cycle times, bottleneck highlights
- **Automation tab**: automatable step candidates, confidence scores
- **Metrics tab**: before/after cycle time, % volume automated, ROI estimate

#### [NEW] `app.py`
Thin entrypoint:
- Calls `theme.apply_theme()`
- Three scenario buttons (A / B / C)
- Imports and renders `dashboard`
- Zero business logic here

---

### Phase 7 — Demo Scenarios (Build Step 5)

Three scripted, reproducible demo scenarios callable via the UI:

| Scenario | Description | Expected Gate Decision |
|---|---|---|
| A | Clean automated approval (receipt check, high confidence, allowlisted) | `APPROVED` |
| B | Policy gate denies out-of-bounds proposal (action not in allowlist) | `DENIED` |
| C | Low confidence triggers human escalation (confidence < 0.80) | `ESCALATED` |

---

### Phase 8 — Documentation

#### [NEW] `README.md`
- Project overview, setup instructions, running locally, deploying to Streamlit Cloud
- Known limitations: synthetic data, prototype thresholds, no production security hardening

#### [NEW] `DEPLOYMENT.md`
- Streamlit Community Cloud setup, secrets configuration, GitHub repo setup

---

## Verification Plan

### Automated Tests
```bash
make test
# or directly:
pytest tests/ -v
```
- All tests pass with no skips
- No test makes live API calls (all use `DeterministicLLMClient`)

### Manual Verification
1. `make run` → Streamlit app opens in browser
2. Dashboard shows DFG and cycle-time metrics on synthetic data
3. Scenario A button → gate approves
4. Scenario B button → gate denies with reason logged
5. Scenario C button → gate escalates with reason logged
6. `audit/decisions_log.jsonl` has all three decisions with full context

---

## Open Questions

> [!IMPORTANT]
> **Groq API Key**: Do you have a Groq API key ready, or should I scaffold the `.env.example` and leave it for you to fill in? The app runs fully on `deterministic` provider without it — but a live key is needed for the Groq scenario.

> [!NOTE]
> **Build order**: I'll follow the exact order in CLAUDE.md — generator → mining → agent/gate → app → scenarios → docs. Each step produces working, tested code before the next step starts. Shall I proceed with the full build in one go, or would you prefer to review after each phase?

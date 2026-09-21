# Process Intelligence + Agentic Automation Engine

> Mine real process patterns from event logs · Identify automation candidates · Gate AI proposals safely with a deterministic engine

---

## What this is

A demonstration system that:
1. **Mines** the as-executed version of an expense-reimbursement process from synthetic event logs (Directly-Follows Graph via `pandas` + `networkx`)
2. **Identifies** which steps are consistent enough to automate
3. **Proposes** automation actions via an LLM (Groq API) — but the LLM **never executes anything directly**
4. **Gates** every proposal through a deterministic confidence/policy/high-impact engine before anything runs

Live demo: _[add Streamlit Cloud URL after first deployment]_

---

## Quick start

### 1. Create the conda environment

```bash
conda create --prefix ./venv python=3.11 -y
```

### 2. Install dependencies

```bash
conda run --no-capture-output --prefix ./venv pip install -e ".[dev]"
```

Or simply:

```bash
make setup
```

### 3. Configure secrets

```bash
cp .env.example .env
# Edit .env and set GROQ_API_KEY (optional — the app works without it using the deterministic provider)
```

### 4. Run the app

```bash
make run
# or: conda run --no-capture-output --prefix ./venv streamlit run app.py
```

### 5. Run tests

```bash
make test
# or: conda run --no-capture-output --prefix ./venv pytest tests/ -v
```

---

## Project structure

```
.
├── app.py                         # Thin Streamlit entrypoint
├── src/process_agent/
│   ├── config.py                  # Single source of truth for settings
│   ├── logging_config.py          # Structured JSON logging
│   ├── generators/log_generator.py
│   ├── mining/process_mining.py   # DFG discovery (no pm4py)
│   ├── agent/
│   │   ├── llm_client.py          # Groq + deterministic clients
│   │   └── gate_engine.py         # Deterministic approval gate
│   └── ui/
│       ├── theme.py               # CSS token injection
│       └── dashboard.py           # Tabbed dashboard
├── tests/                         # pytest suite (no live API calls)
├── data/event_logs.csv            # Generated at first run
├── audit/decisions_log.jsonl      # Append-only gate decision log
├── .streamlit/config.toml         # Theme tokens
└── pyproject.toml
```

---

## Demo scenarios

Run from the **sidebar** inside the app:

| Scenario | Description | Expected gate decision |
|---|---|---|
| **A** | Clean automated approval — high-confidence, allowlisted action | ✅ `APPROVED` |
| **B** | Policy gate denies — action not in the approved allowlist | ❌ `DENIED` |
| **C** | Low confidence triggers human escalation | ⚠️ `ESCALATED` |

Every decision is written to `audit/decisions_log.jsonl` with the full input, decision, and reason.

---

## Architecture principle

**The LLM/agent never executes anything directly.**

It emits a schema-validated `ActionProposal` (JSON). A separate deterministic `GateEngine` checks:
1. Confidence ≥ threshold (default 0.80) — else ESCALATED
2. Action in policy allowlist — else DENIED
3. Action not high-impact — else ESCALATED

Only after all three gates pass does the engine return `APPROVED`.

---

## Tech stack

| Component | Library |
|---|---|
| Process mining | `pandas` + `networkx` (hand-rolled DFG — no pm4py) |
| LLM provider | Groq API (`groq`, OpenAI-compatible) |
| UI | Streamlit |
| Tests | `pytest` |
| Storage | SQLite-compatible CSV + JSONL |
| Deployment | Streamlit Community Cloud |

---

## Known limitations

- **Synthetic data only** — event logs are generated, not from real systems. All metrics and ROI estimates are illustrative.
- **Prototype thresholds** — the 0.80 confidence threshold and policy allowlist are hardcoded defaults chosen for demonstration, not derived from a real risk assessment.
- **No production security hardening** — no authentication, rate limiting, or input sanitisation. Do not expose this to the internet without hardening.
- **Simplified ROI model** — the labour-saving estimate uses a flat £30/hr rate and 2 min/activity assumption. Real ROI depends on actual process costs.
- **DFG only** — this implementation does conformance checking or BPMN discovery; it discovers Directly-Follows Graphs only, which is sufficient for the demo scope.

---

## Deployment

See `DEPLOYMENT.md` for Streamlit Community Cloud setup.

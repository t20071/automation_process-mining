# Process Intelligence + Agentic Automation Engine

## What this project is
A demonstration system that (1) mines the *actual* as-executed version of a business
process from event logs, (2) identifies which steps are repeatable/automatable, and
(3) builds an AI agent that automates those steps safely — using a deterministic gate
layer so the agent can only *propose* actions, never execute them directly.

This is a general-purpose demonstration of grounding agentic automation in real
execution signals, with reliability/compliance built in rather than bolted on.

## Non-negotiable architecture rule
**The LLM/agent never executes anything directly.** It only emits a structured,
schema-validated action proposal (JSON). A separate deterministic engine evaluates
every proposal against confidence, policy, and risk gates before anything runs.
Low-confidence or high-impact proposals escalate to a human-review queue instead of
executing. Do not let any implementation shortcut this boundary, even for "just a
quick test."

## Tech stack
- Python 3.11+
- Process mining: pandas + networkx (custom lightweight DFG discovery) — NOT pm4py.
  pm4py pulls in Graphviz as a native binary dependency, which is unreliable on
  Streamlit Community Cloud. A hand-rolled Directly-Follows Graph using
  `groupby` + `networkx` is simpler to deploy and is enough for this project's
  scope (discovery + cycle-time stats, not conformance checking).
- SQLite for the case/event log store (no external DB dependency)
- Streamlit for both the app UI and the dashboard — single deployable app
- LLM provider: **Groq API** (free tier) as the default "brain" — fast inference,
  OpenAI-compatible endpoint, no local model hosting needed. Keep the provider
  pluggable: `groq` (live demo/deployed app), `deterministic` (tests, canned
  responses, no network call). Drop local Ollama from the deployed path — it's
  useful for local dev/offline demos only, not for the hosted Streamlit app.
- `pytest` for all tests
- Deployment: GitHub (public repo) + Streamlit Community Cloud

## Web design
Before writing any CSS, Streamlit custom styling, or `.streamlit/config.toml`
theme settings, read `docs/design-system.md` and follow it exactly —
color tokens, fonts, status palette, spacing, and radius values are all specified
there. Do not invent a different color palette or font stack.

## Project structure
```
automation_process-mining/
├── app.py                         # THIN entrypoint — Streamlit Cloud main file (do not move)
├── src/process_agent/
│   ├── config.py                  # single source of truth for settings (st.secrets → env → defaults)
│   ├── logging_config.py          # structured JSON logging
│   ├── ingestion/event_log.py     # CSV column auto-detection, validation, normalisation
│   ├── generators/log_generator.py
│   ├── mining/
│   │   ├── process_mining.py      # DFG discovery, activity stats, bottleneck/consistency flags
│   │   ├── analytics.py           # cases, paths, health score, insights, ROI
│   │   └── automation_advisor.py  # rule-based (+ optional Groq) advice
│   ├── agent/
│   │   ├── llm_client.py          # ActionProposal + providers
│   │   └── gate_engine.py         # deterministic gates + audit log + trace()
│   └── ui/
│       ├── state.py               # session state + dataset callbacks
│       ├── analysis.py            # cached per-dataset Analysis bundle
│       ├── workspace.py           # sidebar + tabs
│       ├── components/            # theme.py (tokens, HTML helpers), charts.py
│       └── views/                 # landing, overview, process_map, automation,
│                                  # decision_gate, roi, event_log
├── tests/{unit,integration}/      # pytest, deterministic provider only
├── data/event_logs.csv            # sample synthetic log
├── docs/                          # architecture, design system, deployment, plans, images
├── audit/decisions_log.jsonl      # runtime, gitignored, append-only
└── .streamlit/config.toml         # theme tokens only — no secrets
```

## Process to demonstrate (pick one, keep it concrete)
Default: **expense reimbursement approval**. Variants to include in synthetic logs:
- Happy path: submit → manager approval → finance approval → paid
- Escalation: submit → manager approval → flagged for finance review → paid
- Rejection loop: submit → manager rejects → resubmit → manager approval → paid
- Exception: submit → missing receipt → hold → resolved → paid

## Build order (do not skip ahead)
1. `log_generator.py` + tests — generate ~2,000 synthetic cases across the 4 variants
2. `process_mining.py` + tests — discover the DFG (pandas/networkx) from generated
   logs, compute cycle time per step, flag the top 3 bottleneck/high-variance steps
3. `llm_client.py` + `agent_gate_engine.py` + tests — for one automatable step
   (e.g., "check receipt completeness"), the agent (via Groq API) proposes an
   action; the gate engine checks confidence (default threshold 0.80), policy
   allowlist, and high-impact scrutiny before approving/denying/escalating.
   Tests use the `deterministic` provider — never call the live Groq API in CI.
4. `app.py` — single Streamlit app: a page to run/view demo scenarios, plus the
   dashboard (cycle time before/after, % of case volume automated, ROI estimate).
   Follow `docs/design-system.md` for all styling — inject the color/type tokens
   and set `.streamlit/config.toml` theme values as specified there.
5. Three demo scenarios, scripted for reliability (like Scenario A/B/C in prior work):
   - Scenario A: clean automated approval
   - Scenario B: policy gate denies an out-of-bounds proposal
   - Scenario C: low confidence triggers human escalation
6. Deploy to Streamlit Community Cloud (see docs/deployment.md)

## Coding conventions
- Every module independently testable — no module should require another running
  service to unit test
- Type hints on all function signatures
- No string-interpolated SQL — parameterized queries only
- Every gate decision (approve/deny/escalate) is logged to `audit/decisions_log.jsonl`
  with the full input, decision, and reason — no silent decisions
- Keep functions under ~40 lines; extract helpers rather than growing one function
- **Never hardcode the Groq API key anywhere in code.** Read it only via
  `st.secrets["GROQ_API_KEY"]` (deployed) with an `os.environ.get("GROQ_API_KEY")`
  fallback (local dev). `.streamlit/secrets.toml` must be in `.gitignore` from the
  very first commit — verify this before the first `git push`, not after.

## What "done" looks like
- `pytest` passes with no skipped tests
- Dashboard runs and shows before/after metrics on synthetic data
- All three demo scenarios run reproducibly via a single command each
- README documents known limitations (synthetic data, prototype thresholds, no
  production security hardening) — same honesty standard as prior DPI project

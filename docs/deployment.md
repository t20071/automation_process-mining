# Deployment — Streamlit Community Cloud

**Live app:** https://automationprocess-mining-axwvl7ifpjurzdcrn8ayzy.streamlit.app/

The app is deployed from `t20071/automation_process-mining`, branch `main`, main file
`app.py`. Pushing to `main` redeploys automatically — the URL never changes as long as
the repository, branch and main-file path stay the same.

## Updating the live app

```bash
git add -A
git commit -m "your message"
git push origin main
```

Streamlit Cloud picks up the push within a minute or two. If dependencies changed,
it reinstalls from `requirements.txt` (use **Manage app → Reboot** if a rebuild
looks stuck).

## Secrets (optional)

App settings → **Secrets** (template: `.streamlit/secrets.toml.example`):

```toml
GROQ_API_KEY = "gsk_your_actual_key_here"
LLM_PROVIDER = "groq"
GROQ_MODEL = "llama-3.3-70b-versatile"
```

Without a key the app runs in deterministic mode: every feature works except
LLM-enhanced advice and the live agent.

## First-time deployment (new fork)

1. Push the repository to GitHub (public).
2. [share.streamlit.io](https://share.streamlit.io) → **Create app** → choose repo, branch
   `main`, main file `app.py`.
3. Add secrets (optional) and deploy.

## Checklist after a deploy

- Landing page shows the hero with live demo numbers.
- **Analyse demo dataset** opens the workspace; all six tabs render.
- Decision gate: Scenario A → APPROVED, B → DENIED, C → ESCALATED.

## Environment variables reference

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | Enables LLM-enhanced advice and the live agent |
| `LLM_PROVIDER` | `groq` if a key exists, else `deterministic` | Force a provider |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Any Groq chat model |
| `CONFIDENCE_THRESHOLD` | `0.80` | Gate confidence threshold |
| `NUM_CASES` | `2000` | Size of generated demo logs |

## Notes

- `requirements.txt` is what Streamlit Cloud installs — keep it in sync with `pyproject.toml`.
- Never add `pm4py` or Graphviz binaries: the process map renders DOT in the browser.
- `audit/` is created at runtime and is ephemeral on Streamlit Cloud (resets on reboot).
  Use the in-app **Download audit log** button to keep a copy.

# Deployment — Streamlit Community Cloud

## Prerequisites

- Public GitHub repository containing this project
- Free [Streamlit Community Cloud](https://streamlit.io/cloud) account
- (Optional) Free [Groq API key](https://console.groq.com)

---

## Steps

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "feat: initial project scaffold"
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

> **Verify before pushing**: confirm `.gitignore` includes `.env` and
> `.streamlit/secrets.toml`. Run `git status` and make sure neither file
> appears as "untracked".

### 2. Connect to Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **New app**
3. Select your GitHub repo + branch (`main`)
4. Set **Main file path** to `app.py`
5. Click **Deploy**

### 3. Add secrets

In the Streamlit Cloud dashboard → **Settings → Secrets**, add:

```toml
GROQ_API_KEY = "gsk_your_actual_key_here"
LLM_PROVIDER = "groq"
```

If you leave these blank, the app falls back to the `deterministic` provider
and works without a Groq key.

### 4. Verify

- App loads and shows the Process Map tab with DFG
- Sidebar Scenario A/B/C buttons each produce a gate decision
- `audit/decisions_log.jsonl` accumulates entries (visible in app logs)

---

## Environment variables reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | No | — | Groq API key for live LLM calls |
| `LLM_PROVIDER` | No | `deterministic` | `groq` or `deterministic` |
| `CONFIDENCE_THRESHOLD` | No | `0.80` | Gate confidence threshold |
| `NUM_CASES` | No | `2000` | Synthetic cases to generate |

---

## Notes

- `requirements.txt` is what Streamlit Cloud reads for dependencies — keep it in sync with `pyproject.toml`.
- Do **not** add `pm4py` to requirements — it requires Graphviz as a native binary which is unavailable on Streamlit Cloud.
- The `data/` and `audit/` directories are gitignored; they are created at runtime.

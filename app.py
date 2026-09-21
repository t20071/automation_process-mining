"""
app.py — thin Streamlit entrypoint.

Responsibilities:
  - Apply theme
  - CSV upload page (or demo data fallback)
  - Run process mining on uploaded/demo data
  - Sidebar scenario buttons (A / B / C)
  - Render dashboard

Zero business logic lives here — all logic is in src/process_agent/.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

# Ensure src/ is on the Python path when running directly
sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd
import streamlit as st

from process_agent.agent.gate_engine import GateEngine
from process_agent.agent.llm_client import get_client
from process_agent.config import LLMProvider, get_settings
from process_agent.generators.log_generator import generate_event_log
from process_agent.logging_config import setup_logging
from process_agent.mining.automation_advisor import get_automation_advice
from process_agent.mining.process_mining import discover_process_map
from process_agent.ui.theme import apply_theme, page_header, status_badge

# ──────────────────────────────────────────────────────────────
# Bootstrap (must happen before any st.* call except set_page_config)
# ──────────────────────────────────────────────────────────────
setup_logging()
apply_theme()
settings = get_settings()

# ──────────────────────────────────────────────────────────────
# Session state
# ──────────────────────────────────────────────────────────────
if "df" not in st.session_state:
    st.session_state.df = None
if "source_label" not in st.session_state:
    st.session_state.source_label = ""
if "gate_results" not in st.session_state:
    st.session_state.gate_results = []

# ──────────────────────────────────────────────────────────────
# CSV utilities
# ──────────────────────────────────────────────────────────────

REQUIRED_COLUMNS = {"case_id", "activity", "timestamp", "duration_seconds"}
OPTIONAL_COLUMNS = {"variant", "amount", "submitter_id"}

# Aliases for auto-detection (lowercase, no spaces/underscores)
_ALIASES: dict[str, list[str]] = {
    "case_id":          ["caseid", "case_id", "case", "id", "ticketid", "ticket_id", "claimid", "claim_id", "incident_id"],
    "activity":         ["activity", "activities", "task", "step", "event", "action", "activityname", "activity_name"],
    "timestamp":        ["timestamp", "time", "datetime", "date_time", "starttime", "start_time", "startedat", "started_at", "date"],
    "duration_seconds": ["duration_seconds", "duration", "durationinseconds", "timetaken", "time_taken", "elapsed", "elapsedseconds"],
    "variant":          ["variant", "path", "processpath", "process_path", "processvariant", "flow"],
    "amount":           ["amount", "value", "cost", "price", "total", "claimamount", "amountgbp"],
    "submitter_id":     ["submitter_id", "submitter", "user", "userid", "user_id", "employeeid", "employee_id", "empid"],
}


def _normalise(name: str) -> str:
    return name.lower().replace(" ", "").replace("_", "").replace("-", "")


def _map_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    Auto-detect and rename columns to standard names.
    Returns (renamed_df, mapping_used).
    """
    mapping: dict[str, str] = {}
    cols_normalised = {_normalise(c): c for c in df.columns}

    for standard, aliases in _ALIASES.items():
        if standard in df.columns:
            mapping[standard] = standard
            continue
        for alias in aliases:
            norm = _normalise(alias)
            if norm in cols_normalised:
                mapping[cols_normalised[norm]] = standard
                break

    return df.rename(columns=mapping), mapping


def _validate_csv(df: pd.DataFrame) -> list[str]:
    """Return list of validation error strings (empty = OK)."""
    errors: list[str] = []
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        errors.append(f"Missing required columns: **{', '.join(sorted(missing))}**")
    if df.empty:
        errors.append("The CSV file is empty.")
    if "timestamp" in df.columns:
        try:
            pd.to_datetime(df["timestamp"])
        except Exception:
            errors.append("Column `timestamp` could not be parsed as datetime.")
    if "duration_seconds" in df.columns:
        if not pd.api.types.is_numeric_dtype(df["duration_seconds"]):
            errors.append("Column `duration_seconds` must be numeric.")
    return errors


def _sample_csv_bytes() -> bytes:
    """Generate a downloadable sample CSV."""
    df = generate_event_log(num_cases=20, seed=0)
    return df.to_csv(index=False).encode()


# ──────────────────────────────────────────────────────────────
# Process mining (cached on dataframe hash)
# ──────────────────────────────────────────────────────────────

@st.cache_data(show_spinner="Mining process map…")
def _mine(_df: pd.DataFrame):
    return discover_process_map(_df)


@st.cache_data(show_spinner="Generating automation recommendations…")
def _advise(_df: pd.DataFrame, groq_key: str, groq_model: str):
    pm = discover_process_map(_df)
    return get_automation_advice(pm, groq_api_key=groq_key, groq_model=groq_model)


# ──────────────────────────────────────────────────────────────
# Gate engine
# ──────────────────────────────────────────────────────────────
gate_engine = GateEngine(
    confidence_threshold=settings.confidence_threshold,
    policy_allowlist=settings.policy_allowlist,
    high_impact_actions=settings.high_impact_actions,
    audit_log_path=settings.audit_log_path,
)

# ──────────────────────────────────────────────────────────────
# Demo scenario runner
# ──────────────────────────────────────────────────────────────
_SCENARIO_CONTEXTS = {
    "A": {"case_id": "DEMO-A-001", "activity": "check_receipt_completeness",
          "amount": 350.00, "variant": "happy_path", "submitter_id": "EMP-042"},
    "B": {"case_id": "DEMO-B-001", "activity": "manager_approval",
          "amount": 4_800.00, "variant": "escalation", "submitter_id": "EMP-107"},
    "C": {"case_id": "DEMO-C-001", "activity": "check_receipt_completeness",
          "amount": 1_200.00, "variant": "exception", "submitter_id": "EMP-033"},
}
_SCENARIO_LLM = {"A": "scenario_a", "B": "scenario_b", "C": "scenario_c"}


def _run_scenario(label: str) -> None:
    context = _SCENARIO_CONTEXTS[label]
    provider = (
        settings.llm_provider.value
        if settings.llm_provider == LLMProvider.GROQ and settings.groq_api_key
        else "deterministic"
    )
    client = get_client(
        provider=provider,
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        scenario=_SCENARIO_LLM[label],
    )
    proposal = client.propose_action(context)
    result = gate_engine.evaluate(proposal, context)
    st.session_state.gate_results.append({
        "scenario": label,
        "decision": result.decision.value,
        "reason": result.reason,
        "proposal": {
            "action": proposal.action,
            "confidence": proposal.confidence,
            "reasoning": proposal.reasoning,
            "affected_fields": proposal.affected_fields,
        },
        "context": context,
    })


# ──────────────────────────────────────────────────────────────
# Page header (always shown)
# ──────────────────────────────────────────────────────────────
st.markdown(
    page_header(
        "Process Intelligence Engine",
        "Upload your event log · Mine process patterns · Get automation recommendations",
    ),
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────────────────────
# UPLOAD PAGE — shown when no data is loaded
# ──────────────────────────────────────────────────────────────
if st.session_state.df is None:
    st.markdown(
        """
        <div style="
            background: var(--stone-50);
            border-radius: var(--radius-2xl);
            padding: 2rem 2.5rem;
            border: 1px solid var(--stone-100);
            margin-bottom: 1.5rem;
        ">
        <h2 style="font-family:'DM Serif Display',serif;font-size:1.4rem;
                   letter-spacing:-0.02em;margin:0 0 0.5rem;">
            Upload your event log CSV
        </h2>
        <p style="color:var(--gray);font-size:0.9rem;margin:0 0 1rem;">
            The file must contain these columns:
        </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Column guide
    col_guide = pd.DataFrame([
        {"Column", "Required", "Example"},
        {"case_id", "✅ Yes", "TICKET-001"},
        {"activity", "✅ Yes", "manager_approval"},
        {"timestamp", "✅ Yes", "2024-01-15 09:30:00"},
        {"duration_seconds", "✅ Yes", "3600"},
        {"variant", "❌ Optional", "happy_path"},
        {"amount", "❌ Optional", "450.00"},
        {"submitter_id", "❌ Optional", "EMP-042"},
    ])
    st.markdown("""
| Column | Required | Example |
|---|---|---|
| `case_id` | ✅ Required | `TICKET-001` |
| `activity` | ✅ Required | `manager_approval` |
| `timestamp` | ✅ Required | `2024-01-15 09:30:00` |
| `duration_seconds` | ✅ Required | `3600` |
| `variant` | ❌ Optional | `happy_path` |
| `amount` | ❌ Optional | `450.00` |
| `submitter_id` | ❌ Optional | `EMP-042` |
""")

    # Column names are auto-detected — common aliases supported
    st.caption(
        "💡 Column names are auto-detected. Common aliases like `Case ID`, "
        "`task`, `elapsed`, `user_id` are all recognised."
    )

    # Sample CSV download
    st.download_button(
        label="⬇️  Download sample CSV",
        data=_sample_csv_bytes(),
        file_name="sample_event_log.csv",
        mime="text/csv",
        key="dl_sample",
    )

    st.divider()

    # Upload widget
    uploaded = st.file_uploader(
        "Choose a CSV file",
        type=["csv"],
        key="csv_uploader",
        label_visibility="collapsed",
    )

    if uploaded is not None:
        raw_df = pd.read_csv(uploaded)
        mapped_df, col_map = _map_columns(raw_df)
        errors = _validate_csv(mapped_df)

        if errors:
            st.error("**Could not process this file:**\n\n" + "\n\n".join(f"- {e}" for e in errors))
            if col_map:
                st.info(f"Detected column mapping: `{col_map}`")
        else:
            # Add missing optional columns with defaults
            if "variant" not in mapped_df.columns:
                mapped_df["variant"] = "unknown"
            if "amount" not in mapped_df.columns:
                mapped_df["amount"] = 0.0
            if "submitter_id" not in mapped_df.columns:
                mapped_df["submitter_id"] = "unknown"
            mapped_df["timestamp"] = pd.to_datetime(mapped_df["timestamp"])
            mapped_df["duration_seconds"] = pd.to_numeric(mapped_df["duration_seconds"])

            st.session_state.df = mapped_df
            st.session_state.source_label = f"📄 {uploaded.name}"
            st.session_state.gate_results = []
            st.success(
                f"✅ Loaded **{mapped_df['case_id'].nunique():,} cases** "
                f"/ **{len(mapped_df):,} events** from `{uploaded.name}`"
            )
            st.rerun()

    # Demo data option
    st.divider()
    st.markdown(
        "<p style='color:var(--gray);font-size:0.9rem;text-align:center;'>— or —</p>",
        unsafe_allow_html=True,
    )
    if st.button("🎭  Use demo data (expense reimbursement, 2,000 cases)", key="btn_demo"):
        with st.spinner("Generating 2,000 synthetic expense reimbursement cases…"):
            df = generate_event_log(num_cases=2_000, seed=42)
        st.session_state.df = df
        st.session_state.source_label = "🎭 Demo data"
        st.session_state.gate_results = []
        st.rerun()

    st.stop()   # Don't render dashboard until data is loaded

# ──────────────────────────────────────────────────────────────
# DASHBOARD — shown when data is loaded
# ──────────────────────────────────────────────────────────────
df = st.session_state.df
process_map = _mine(df)
advice_list = _advise(
    df,
    groq_key=settings.groq_api_key if settings.llm_provider == LLMProvider.GROQ else "",
    groq_model=settings.groq_model,
)

# ── Sidebar ──
with st.sidebar:
    st.markdown(
        f"<p style='font-size:0.8rem;color:var(--gray);'>"
        f"Source: {st.session_state.source_label}</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"**{df['case_id'].nunique():,}** cases · **{len(df):,}** events",
    )
    if st.button("🔄  Upload new file", key="btn_reset"):
        st.session_state.df = None
        st.session_state.gate_results = []
        st.rerun()

    st.divider()
    st.markdown(
        "<h3 style='font-size:1rem;font-weight:600;margin-bottom:0.5rem;'>"
        "⚡ Gate Engine Demo</h3>",
        unsafe_allow_html=True,
    )
    st.caption("Run a scripted case through the gate engine. Results appear in the **Gate Demo** tab.")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("▶ A", key="btn_a", help="Scenario A — Auto-approved", use_container_width=True):
            _run_scenario("A"); st.rerun()
    with col_b:
        if st.button("▶ B", key="btn_b", help="Scenario B — Policy denied", use_container_width=True):
            _run_scenario("B"); st.rerun()
    with col_c:
        if st.button("▶ C", key="btn_c", help="Scenario C — Escalated", use_container_width=True):
            _run_scenario("C"); st.rerun()

    if st.button("🗑 Clear results", key="btn_clear", use_container_width=True):
        st.session_state.gate_results = []
        st.rerun()

    st.divider()
    st.markdown(
        "| | Scenario |\n|---|---|\n"
        "| **A** | ✅ Clean auto-approval |\n"
        "| **B** | ❌ Policy gate denies |\n"
        "| **C** | ⚠️ Low confidence escalates |"
    )
    st.markdown(
        f"\n**Provider**: `{settings.llm_provider.value}`  \n"
        f"**Confidence threshold**: `{settings.confidence_threshold}`"
    )

# ── Main dashboard ──
from process_agent.ui.dashboard import render_dashboard
render_dashboard(process_map, st.session_state.gate_results, advice_list)

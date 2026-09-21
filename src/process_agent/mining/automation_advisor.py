"""
src/process_agent/mining/automation_advisor.py

Generates per-activity automation recommendations.

Two modes:
  - Rule-based (default): fast, no API cost, pattern + stats driven
  - LLM-enhanced (when Groq key present): single batched Groq call for
    richer, context-aware recommendations

Public API
----------
get_automation_advice(process_map, settings) -> list[ActivityAdvice]
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from process_agent.mining.process_mining import ActivityStats, ProcessMap

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ActivityAdvice:
    activity: str
    status: str                      # "automatable" | "review" | "bottleneck"
    status_emoji: str                # ✅ ⚠️ 🔴
    status_label: str                # display text
    reason: str                      # why this classification
    how_to_automate: str             # actionable recommendation
    tools_suggested: list[str]       # specific tools / approaches
    estimated_saving_pct: float      # rough % of step time that can be saved
    source: str = "rule"             # "rule" or "llm"


# ---------------------------------------------------------------------------
# Rule-based recommendation engine
# ---------------------------------------------------------------------------

# keyword → (tools list, how-to text, saving %)
_KEYWORD_RULES: list[tuple[list[str], list[str], str, float]] = [
    (
        ["submit", "submission", "request", "raise", "create"],
        ["Web form", "REST API", "RPA bot"],
        "Automate via a web form with built-in field validation and auto-population "
        "from user profile. Connect to backend via REST API to eliminate manual data entry.",
        0.90,
    ),
    (
        ["check", "verify", "validate", "validation", "completeness"],
        ["Rule engine", "AI document processing", "OCR"],
        "Apply rule-based validation (required fields, format checks) or an AI document "
        "model (e.g. AWS Textract, Azure Form Recognizer) to verify completeness in seconds.",
        0.95,
    ),
    (
        ["flag", "duplicate", "detect", "deduplicate"],
        ["Hash comparison", "Database lookup"],
        "Detect duplicates by hashing key fields (amount + submitter + date range) "
        "and comparing against existing records in the database.",
        0.98,
    ),
    (
        ["paid", "payment", "pay", "reimburse", "transfer", "disburse"],
        ["Banking API", "Payment gateway", "ERP trigger"],
        "Trigger payment automatically via banking API or ERP payment module once all "
        "upstream approvals are collected. Use webhooks to confirm settlement.",
        0.85,
    ),
    (
        ["notify", "notification", "alert", "email", "message"],
        ["Email API", "Slack/Teams bot", "SMS gateway"],
        "Send automated status notifications via email (SendGrid, SES) or messaging "
        "platform (Slack, Teams) at each key transition.",
        0.99,
    ),
    (
        ["resolve", "resolution", "fix", "correct", "remedy"],
        ["Workflow engine", "Decision tree", "Exception handler"],
        "Auto-resolve common exceptions using a decision tree of known resolution paths. "
        "Route only novel exceptions to humans.",
        0.70,
    ),
    (
        ["category", "categorise", "categorize", "classify", "code"],
        ["ML classifier", "Lookup table", "NLP model"],
        "Map to expense categories using a lookup table of merchant codes or a "
        "lightweight ML text classifier trained on historical approved claims.",
        0.92,
    ),
    (
        ["receipt", "document", "attachment", "scan", "image"],
        ["OCR engine", "AI vision model", "Document parser"],
        "Use an OCR engine or AI vision model to extract and validate receipt data "
        "(merchant, amount, date) without manual review.",
        0.88,
    ),
]

# Activities that are human-judgment steps — no full automation
_REVIEW_KEYWORDS = [
    "approval", "approve", "review", "decision", "authorize", "authorise",
    "sign", "sign-off", "signoff", "escalate", "escalation",
]

# Activities that are typically exception / hold states
_EXCEPTION_KEYWORDS = [
    "hold", "wait", "pending", "exception", "reject", "resubmit",
    "missing", "incomplete", "dispute",
]


def _match_keyword(activity: str, keywords: list[str]) -> bool:
    act = activity.lower().replace("_", " ").replace("-", " ")
    return any(kw in act for kw in keywords)


def _rule_based_advice(stats: ActivityStats) -> ActivityAdvice:
    """Generate rule-based advice for a single activity."""
    activity = stats.activity

    # Check if it's a human-judgment / review step
    if _match_keyword(activity, _REVIEW_KEYWORDS):
        return ActivityAdvice(
            activity=activity,
            status="review",
            status_emoji="⚠️",
            status_label="Human Required",
            reason=(
                f"Approval/review steps require human judgment. "
                f"Avg {_fmt_dur(stats.mean_seconds)}, std {_fmt_dur(stats.std_seconds)} — "
                "high variance confirms inconsistent case complexity."
            ),
            how_to_automate=(
                "Cannot be fully automated. Streamline with an approval workflow tool "
                "(Slack bot, Microsoft Power Automate) to reduce wait time without "
                "removing human oversight."
            ),
            tools_suggested=["Slack Workflow Builder", "Power Automate", "Jira Service Desk"],
            estimated_saving_pct=0.30,  # workflow tooling saves ~30%
            source="rule",
        )

    # Check if it's a hold/exception step
    if _match_keyword(activity, _EXCEPTION_KEYWORDS) or stats.is_bottleneck:
        return ActivityAdvice(
            activity=activity,
            status="bottleneck",
            status_emoji="🔴",
            status_label="Bottleneck",
            reason=(
                f"High variance (std {_fmt_dur(stats.std_seconds)}) signals unpredictable "
                f"exceptions. Avg cycle time: {_fmt_dur(stats.mean_seconds)}, "
                f"P95: {_fmt_dur(stats.p95_seconds)}."
            ),
            how_to_automate=(
                "Focus on upstream prevention rather than automating the exception itself. "
                "Add pre-submission validation to catch issues earlier and reduce how often "
                "this step is reached."
            ),
            tools_suggested=["Pre-submission validation", "SLA tracking dashboard", "Exception analytics"],
            estimated_saving_pct=0.20,
            source="rule",
        )

    # Try keyword matching for automatable steps
    for keywords, tools, how_to, saving in _KEYWORD_RULES:
        if _match_keyword(activity, keywords) and stats.is_automatable:
            return ActivityAdvice(
                activity=activity,
                status="automatable",
                status_emoji="✅",
                status_label="Automatable",
                reason=(
                    f"Low variance (CV ≤ 30%) — consistent, predictable execution. "
                    f"Avg {_fmt_dur(stats.mean_seconds)}, "
                    f"std {_fmt_dur(stats.std_seconds)} across {stats.count} cases."
                ),
                how_to_automate=how_to,
                tools_suggested=tools,
                estimated_saving_pct=saving,
                source="rule",
            )

    # Automatable by stats but no keyword match
    if stats.is_automatable:
        return ActivityAdvice(
            activity=activity,
            status="automatable",
            status_emoji="✅",
            status_label="Automatable",
            reason=(
                f"Consistent execution (CV ≤ 30%). "
                f"Avg {_fmt_dur(stats.mean_seconds)}, std {_fmt_dur(stats.std_seconds)}."
            ),
            how_to_automate=(
                "This step shows consistent, predictable behaviour. Implement via RPA bot "
                "or script that replicates the manual steps deterministically."
            ),
            tools_suggested=["RPA (UiPath / Automation Anywhere)", "Python script", "Zapier"],
            estimated_saving_pct=0.75,
            source="rule",
        )

    # Default: standard step, not flagged either way
    return ActivityAdvice(
        activity=activity,
        status="review",
        status_emoji="⚠️",
        status_label="Review Recommended",
        reason=(
            f"Moderate variance. Avg {_fmt_dur(stats.mean_seconds)}, "
            f"std {_fmt_dur(stats.std_seconds)} — assess case-by-case."
        ),
        how_to_automate=(
            "Pilot automation on a subset of cases first. Monitor accuracy "
            "before rolling out fully."
        ),
        tools_suggested=["Pilot RPA", "A/B test automation"],
        estimated_saving_pct=0.50,
        source="rule",
    )


def _fmt_dur(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3_600:
        return f"{seconds / 60:.0f}m"
    if seconds < 86_400:
        return f"{seconds / 3_600:.1f}h"
    return f"{seconds / 86_400:.1f}d"


# ---------------------------------------------------------------------------
# LLM-enhanced path (single batched Groq call)
# ---------------------------------------------------------------------------

_BATCH_SYSTEM_PROMPT = """You are a process automation expert.
Given a list of business process activities with their cycle-time statistics,
provide a JSON array of automation recommendations.

For each activity return:
{
  "activity": "<name>",
  "status": "automatable" | "review" | "bottleneck",
  "how_to_automate": "<1-2 sentence practical recommendation>",
  "tools_suggested": ["<tool1>", "<tool2>"],
  "estimated_saving_pct": <0.0-1.0>
}

Rules:
- automatable: consistent, low-variance, rule-following steps
- review: requires human judgment (approvals, decisions)
- bottleneck: high-variance, unpredictable, exception-prone
- how_to_automate: must be specific and actionable, not generic
- Return ONLY the JSON array, no other text
"""


def _llm_enhance(
    advice_list: list[ActivityAdvice],
    stats_map: dict[str, ActivityStats],
    api_key: str,
    model: str = "llama3-8b-8192",
) -> list[ActivityAdvice]:
    """
    Make a single batched Groq call to enrich all rule-based advice.
    Falls back to rule-based on any error.
    """
    try:
        from groq import Groq  # type: ignore[import]

        activities_payload = [
            {
                "activity": s.activity,
                "mean_seconds": round(s.mean_seconds, 0),
                "std_seconds": round(s.std_seconds, 0),
                "p95_seconds": round(s.p95_seconds, 0),
                "count": s.count,
                "is_bottleneck": s.is_bottleneck,
                "is_automatable": s.is_automatable,
            }
            for s in stats_map.values()
        ]
        user_msg = (
            "Provide automation recommendations for these process activities:\n"
            + json.dumps(activities_payload, indent=2)
        )

        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _BATCH_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
            max_tokens=2048,
        )
        raw = completion.choices[0].message.content or "[]"
        llm_data: list[dict] = json.loads(raw.strip())

        # Merge LLM output into advice list
        llm_map = {item["activity"]: item for item in llm_data}
        enhanced: list[ActivityAdvice] = []
        for adv in advice_list:
            llm = llm_map.get(adv.activity)
            if llm:
                adv.how_to_automate = llm.get("how_to_automate", adv.how_to_automate)
                adv.tools_suggested = llm.get("tools_suggested", adv.tools_suggested)
                adv.estimated_saving_pct = float(
                    llm.get("estimated_saving_pct", adv.estimated_saving_pct)
                )
                adv.source = "llm"
            enhanced.append(adv)
        logger.info("LLM-enhanced automation advice", extra={"count": len(enhanced)})
        return enhanced

    except Exception as exc:
        logger.warning(
            "LLM enhancement failed, using rule-based advice",
            extra={"error": str(exc)},
        )
        return advice_list


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_automation_advice(
    process_map: ProcessMap,
    groq_api_key: str = "",
    groq_model: str = "llama3-8b-8192",
) -> list[ActivityAdvice]:
    """
    Return automation advice for every activity in the process map.

    Parameters
    ----------
    process_map   : Output of discover_process_map()
    groq_api_key  : If provided, enriches with a single batched Groq call.
    groq_model    : Groq model to use.

    Returns
    -------
    List of ActivityAdvice sorted: automatable first, then review, then bottleneck.
    """
    advice_list = [
        _rule_based_advice(stats)
        for stats in process_map.activity_stats.values()
    ]

    # LLM enhancement if key available
    if groq_api_key:
        advice_list = _llm_enhance(
            advice_list, process_map.activity_stats, groq_api_key, groq_model
        )

    # Sort: automatable → review → bottleneck
    order = {"automatable": 0, "review": 1, "bottleneck": 2}
    advice_list.sort(key=lambda a: order.get(a.status, 3))
    return advice_list

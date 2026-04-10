"""Response envelope, schema version, and profile-based field filtering.

Provides the structural framing for all Drift API responses — schema
versioning, scope descriptors, and response-profile filtering (ADR-025
Phase B).
"""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "2.1"


def build_drift_score_scope(
    *,
    context: str,
    path: str | None = None,
    signal_scope: str = "all",
    baseline_filtered: bool = False,
) -> str:
    """Return a stable scope descriptor for drift_score values."""
    normalized_path = (path or "all").strip("/") or "all"
    parts = [
        f"context:{context}",
        f"signals:{signal_scope}",
        f"path:{normalized_path}",
    ]
    if baseline_filtered:
        parts.append("baseline:filtered")
    return ",".join(parts)


def _base_response(**extra: Any) -> dict[str, Any]:
    """Build the common response envelope."""
    return {"schema_version": SCHEMA_VERSION, **extra}


# ---------------------------------------------------------------------------
# Response profiles (ADR-025 Phase B) — typed handoffs
# ---------------------------------------------------------------------------

VALID_RESPONSE_PROFILES = ("planner", "coder", "verifier", "merge_readiness")

# Fields that each profile retains.  Unlisted fields are stripped.
# "schema_version", "status", "agent_instruction" are always kept.
_PROFILE_KEEP: dict[str, frozenset[str]] = {
    "planner": frozenset(
        {
            "task_graph",
            "workflow_plan",
            "tasks",
            "execution_phases",
            "next_tool_call",
            "fallback_tool_call",
            "done_when",
            "drift_score",
            "severity",
            "finding_count",
            "top_signals",
            "scope",
            "guardrails",
            "guardrails_prompt_block",
            "risk_summary",
            "landscape",
            "trend",
            "warnings",
            "session",
        }
    ),
    "coder": frozenset(
        {
            "findings",
            "finding_count",
            "fix_first",
            "tasks",
            "drift_score",
            "severity",
            "negative_context",
            "items_returned",
            "next_tool_call",
            "fallback_tool_call",
            "done_when",
            "guardrails",
            "guardrails_prompt_block",
            "session",
        }
    ),
    "verifier": frozenset(
        {
            "drift_score",
            "score_delta",
            "safe_to_commit",
            "direction",
            "confidence_map",
            "severity",
            "new_findings",
            "resolved_findings",
            "accept_change",
            "blocking_reasons",
            "done_when",
            "next_tool_call",
            "fallback_tool_call",
            "tasks",
            "drift_detected",
            "resolved_count",
            "new_count",
            "resolved_count_by_rule",
            "session",
        }
    ),
    "merge_readiness": frozenset(
        {
            "drift_score",
            "severity",
            "score_delta",
            "drift_detected",
            "accept_change",
            "blocking_reasons",
            "warnings",
            "trend",
            "finding_count",
            "top_signals",
            "done_when",
            "session",
        }
    ),
}

_ALWAYS_KEEP = frozenset(
    {
        "schema_version",
        "status",
        "agent_instruction",
        "response_profile",
    }
)


def shape_for_profile(
    result: dict[str, Any],
    profile: str | None,
) -> dict[str, Any]:
    """Filter response fields to match a response profile.

    If *profile* is ``None`` or unrecognised the result is returned unchanged
    (with a ``response_profile`` key set to ``"full"``).
    """
    if not profile or profile not in _PROFILE_KEEP:
        result["response_profile"] = "full"
        return result

    keep = _PROFILE_KEEP[profile] | _ALWAYS_KEEP
    shaped = {k: v for k, v in result.items() if k in keep}
    shaped["response_profile"] = profile
    return shaped

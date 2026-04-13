"""Shared helper utilities for the public drift API module.

This module provides unique API serialisation helpers and re-exports
signal mapping, response-shaping, finding-rendering, task-graph, and
error-response symbols consumed by ``drift.api``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from drift.config import DriftConfig
from drift.finding_context import classify_finding_context
from drift.finding_priority import (
    _SEVERITY_RANK,
    _dedupe_findings,
    _expected_benefit_for_finding,
    _next_step_for_finding,
    _priority_class,
    _priority_rank,
)

# --- Re-exports: finding rendering ---
from drift.finding_rendering import (  # noqa: F401
    _finding_fingerprint_value,
    _signal_weight,
    _top_signals,
    _trend_dict,
    severity_rank,
)
from drift.models import OUTPUT_SCHEMA_VERSION

# --- Re-exports: next-step contracts ---
from drift.next_step_contract import (  # noqa: F401
    DONE_ACCEPT_CHANGE,
    DONE_DIFF_ACCEPT,
    DONE_NO_FINDINGS,
    DONE_NUDGE_SAFE,
    DONE_SAFE_TO_COMMIT,
    DONE_STAGED_EXISTS,
    DONE_TASK_AND_NUDGE,
    DONE_TASKS_COMPLETE,
    _error_response,
    _next_step_contract,
    _tool_call,
)

# --- Re-exports: response shaping ---
from drift.response_shaping import (  # noqa: F401
    _ALWAYS_KEEP,
    _PROFILE_KEEP,
    build_drift_score_scope,
    shape_for_profile,
)

# --- Re-exports: signal mapping ---
from drift.signal_mapping import (  # noqa: F401
    _ABBREV_TO_SIGNAL,
    _SIGNAL_TO_ABBREV,
    VALID_SIGNAL_IDS,
    resolve_signal,
    signal_abbrev,
    signal_abbrev_map,
    signal_scope_label,
)

# --- Re-exports: task graph ---
from drift.task_graph import (  # noqa: F401
    _DEFAULT_INVALIDATION_TRIGGERS,
    _PATCH_SHAPE_DEFAULTS,
    PlanValidationResult,
    TaskGraph,
    WorkflowPlan,
    WorkflowStep,
    _capture_repo_state,
    _compute_plan_fingerprint,
    _derive_repair_exemplar,
    _derive_task_contract,
    _git_cmd,
    _task_to_api_dict,
    build_task_graph,
    build_workflow_plan,
    validate_plan,
)

logger = logging.getLogger("drift")

if TYPE_CHECKING:
    from drift.models import RepoAnalysis

SCHEMA_VERSION = OUTPUT_SCHEMA_VERSION

VALID_RESPONSE_PROFILES = ("planner", "coder", "verifier", "merge_readiness")


def _base_response(**extra: Any) -> dict[str, Any]:
    """Build the common response envelope."""
    return {"schema_version": SCHEMA_VERSION, **extra}


# ---------------------------------------------------------------------------
# Finding serialisation helpers unique to this module
# ---------------------------------------------------------------------------


def finding_base_payload(f: Any) -> dict[str, Any]:
    """Return the shared slim finding payload used by concise serializers."""
    fp = _finding_fingerprint_value(f)
    return {
        "finding_id": fp,
        "signal": signal_abbrev(f.signal_type),
        "signal_abbrev": signal_abbrev(f.signal_type),
        "signal_id": signal_abbrev(f.signal_type),
        "signal_type": f.signal_type,
        "rule_id": f.rule_id,
        "severity": f.severity.value,
        "severity_rank": severity_rank(f.severity.value),
        "title": f.title,
        "file": f.file_path.as_posix() if f.file_path else None,
        "line": f.start_line,
        "start_line": f.start_line,
        "end_line": f.end_line,
        "logical_location": {
            "fully_qualified_name": f.logical_location.fully_qualified_name,
            "name": f.logical_location.name,
            "kind": f.logical_location.kind,
            "class_name": f.logical_location.class_name,
            "namespace": f.logical_location.namespace,
        } if getattr(f, "logical_location", None) else None,
        "finding_context": classify_finding_context(f, DriftConfig()),
        "fingerprint": fp,
    }


def _finding_concise(f: Any) -> dict[str, Any]:
    """Minimal finding dict for concise responses."""
    payload = finding_base_payload(f)
    payload["next_step"] = _next_step_for_finding(f)
    return payload


def _finding_detailed(f: Any, *, rank: int | None = None) -> dict[str, Any]:
    """Full finding dict for detailed responses."""
    from drift.recommendations import generate_recommendation

    rec = generate_recommendation(f)
    base = finding_base_payload(f)
    return {
        **base,
        "score": f.score,
        "impact": f.impact,
        "score_contribution": f.score_contribution,
        "priority_class": _priority_class(f),
        "title": f.title,
        "description": f.description,
        "fix": f.fix,
        "symbol": f.symbol,
        "related_files": [rf.as_posix() for rf in f.related_files],
        "next_step": _next_step_for_finding(f),
        "expected_benefit": _expected_benefit_for_finding(f),
        "remediation": {
            "title": rec.title,
            "description": rec.description,
            "effort": rec.effort,
            "impact": rec.impact,
        }
        if rec
        else None,
    }


def _fix_first_concise(analysis: RepoAnalysis, max_items: int = 5) -> list[dict[str, Any]]:
    """Build compact fix_first list (deduplicated)."""
    deduped, _counts = _dedupe_findings(analysis.findings)

    prioritized = sorted(
        deduped,
        key=lambda f: (
            _priority_rank(_priority_class(f)),
            _SEVERITY_RANK[f.severity],
            -float(f.impact),
        ),
    )

    seen_file_signal: set[tuple[str, str]] = set()
    unique: list = []
    for f in prioritized:
        fp = f.file_path.as_posix() if f.file_path else ""
        key = (fp, f.signal_type)
        if key not in seen_file_signal:
            seen_file_signal.add(key)
            unique.append(f)

    items: list[dict[str, Any]] = []
    for idx, f in enumerate(unique[:max_items], start=1):
        signal = signal_abbrev(f.signal_type)
        severity = f.severity.value
        items.append(
            {
                "rank": idx,
                "signal": signal,
                "signal_abbrev": signal,
                "signal_id": signal,
                "signal_type": f.signal_type,
                "severity": severity,
                "severity_rank": severity_rank(severity),
                "title": f.title,
                "file": f.file_path.as_posix() if f.file_path else None,
                "line": f.start_line,
                "finding_context": classify_finding_context(f, DriftConfig()),
                "fingerprint": _finding_fingerprint_value(f),
                "next_step": _next_step_for_finding(f),
                "expected_benefit": _expected_benefit_for_finding(f),
            }
        )
    return items


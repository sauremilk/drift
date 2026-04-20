# ruff: noqa: F401

"""Programmatic API for drift analysis — agent-native, JSON-first.

This package provides the formalized public interface consumed by both the
MCP server and the CLI.  All functions return typed result dicts (not raw
``RepoAnalysis`` objects) so callers always receive a stable, serialisable
contract.

Backward-compatible re-export surface: every symbol that was previously
available via ``from drift.api import X`` continues to work unchanged.

Stability contract:
        - Symbols in ``STABLE_API`` are the supported public API surface.
        - Symbols in ``LEGACY_API`` are backward-compatibility re-exports and may
            evolve faster; prefer ``STABLE_API`` for new integrations.
"""

from __future__ import annotations

# -- Internal symbols used externally (tests, commands) ---------------------
from drift.api._config import _emit_api_telemetry

# -- Utility ----------------------------------------------------------------
from drift.api._util import to_json

# -- Public endpoints -------------------------------------------------------
from drift.api.brief import brief
from drift.api.compile_policy import compile_policy
from drift.api.diff import _diff_next_actions, diff
from drift.api.drift_map_api import drift_map
from drift.api.explain import _repo_examples_for_signal, explain
from drift.api.fix_apply import fix_apply
from drift.api.fix_plan import _fix_plan_agent_instruction, fix_plan
from drift.api.generate_skills import generate_skills
from drift.api.guard_contract import guard_contract
from drift.api.neg_context import negative_context
from drift.api.nudge import _baseline_store, invalidate_nudge_baseline, nudge
from drift.api.patch import patch_begin, patch_check, patch_commit
from drift.api.scan import (
    _BATCH_SCAN_THRESHOLD,
    _DIVERSE_MIN_TOP_IMPACT_SHARE,
    _diverse_findings,
    _format_scan_response,
    _scan_agent_instruction,
    _scan_next_actions,
    scan,
)
from drift.api.shadow_verify import shadow_verify
from drift.api.steer import steer
from drift.api.suggest_rules import suggest_rules
from drift.api.validate import validate
from drift.api.verify import verify

# Backward-compat: all symbols formerly available as ``drift.api.X``
from drift.api_helpers import (
    DONE_ACCEPT_CHANGE,
    DONE_DIFF_ACCEPT,
    DONE_NO_FINDINGS,
    DONE_NUDGE_SAFE,
    DONE_SAFE_TO_COMMIT,
    DONE_STAGED_EXISTS,
    DONE_TASK_AND_NUDGE,
    VALID_SIGNAL_IDS,
    _base_response,
    _error_response,
    _finding_concise,
    _finding_detailed,
    _fix_first_concise,
    _next_step_contract,
    _task_to_api_dict,
    _top_signals,
    _trend_dict,
    build_drift_score_scope,
    build_task_graph,
    build_workflow_plan,
    resolve_signal,
    severity_rank,
    shape_for_profile,
    signal_abbrev,
    signal_abbrev_map,
    signal_scope_label,
)
from drift.finding_context import is_non_operational_context, split_findings_by_context

STABLE_API = [
    # Stable public endpoints
    "brief",
    "compile_policy",
    "diff",
    "drift_map",
    "explain",
    "fix_plan",
    "fix_apply",
    "negative_context",
    "nudge",
    "invalidate_nudge_baseline",
    "patch_begin",
    "patch_check",
    "patch_commit",
    "scan",
    "shadow_verify",
    "generate_skills",
    "guard_contract",
    "steer",
    "suggest_rules",
    "validate",
    "verify",
    "to_json",
]

LEGACY_API = [
    # Internal (kept for backward compatibility)
    "_baseline_store",
    "_BATCH_SCAN_THRESHOLD",
    "_diff_next_actions",
    "_DIVERSE_MIN_TOP_IMPACT_SHARE",
    "_diverse_findings",
    "_emit_api_telemetry",
    "_fix_plan_agent_instruction",
    "_format_scan_response",
    "_repo_examples_for_signal",
    "_scan_agent_instruction",
    "_scan_next_actions",
    # Backward-compat exports from drift.api_helpers
    "DONE_ACCEPT_CHANGE",
    "DONE_DIFF_ACCEPT",
    "DONE_NO_FINDINGS",
    "DONE_NUDGE_SAFE",
    "DONE_SAFE_TO_COMMIT",
    "DONE_STAGED_EXISTS",
    "DONE_TASK_AND_NUDGE",
    "VALID_SIGNAL_IDS",
    "_base_response",
    "_error_response",
    "_finding_concise",
    "_finding_detailed",
    "_fix_first_concise",
    "_next_step_contract",
    "_task_to_api_dict",
    "_top_signals",
    "_trend_dict",
    "build_drift_score_scope",
    "build_task_graph",
    "build_workflow_plan",
    "resolve_signal",
    "severity_rank",
    "shape_for_profile",
    "signal_abbrev",
    "signal_abbrev_map",
    "signal_scope_label",
    # Backward-compat exports from drift.finding_context
    "is_non_operational_context",
    "split_findings_by_context",
]

__all__ = [*STABLE_API, *LEGACY_API]

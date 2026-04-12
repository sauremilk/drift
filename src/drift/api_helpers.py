"""Shared helper utilities for the public drift API module.

This module contains reusable signal mapping and response-shaping helpers that
are consumed by ``drift.api``. Keeping helpers here reduces api.py size while
preserving the existing public API surface.
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from drift.config import DriftConfig
from drift.finding_context import classify_finding_context
from drift.models import OUTPUT_SCHEMA_VERSION, SignalType
from drift.response_shaping import build_drift_score_scope as _build_drift_score_scope
from drift.signal_mapping import resolve_signal as _resolve_signal
from drift.signal_mapping import signal_scope_label as _signal_scope_label

logger = logging.getLogger("drift")

if TYPE_CHECKING:
    from drift.models import AgentTask, RepoAnalysis


SCHEMA_VERSION = OUTPUT_SCHEMA_VERSION


_SEVERITY_RANK: dict[str, int] = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "info": 1,
}


_ABBREV_TO_SIGNAL: dict[str, SignalType] = {
    "PFS": SignalType.PATTERN_FRAGMENTATION,
    "AVS": SignalType.ARCHITECTURE_VIOLATION,
    "MDS": SignalType.MUTANT_DUPLICATE,
    "TVS": SignalType.TEMPORAL_VOLATILITY,
    "EDS": SignalType.EXPLAINABILITY_DEFICIT,
    "SMS": SignalType.SYSTEM_MISALIGNMENT,
    "DIA": SignalType.DOC_IMPL_DRIFT,
    "BEM": SignalType.BROAD_EXCEPTION_MONOCULTURE,
    "TPD": SignalType.TEST_POLARITY_DEFICIT,
    "GCD": SignalType.GUARD_CLAUSE_DEFICIT,
    "NBV": SignalType.NAMING_CONTRACT_VIOLATION,
    "BAT": SignalType.BYPASS_ACCUMULATION,
    "ECM": SignalType.EXCEPTION_CONTRACT_DRIFT,
    "COD": SignalType.COHESION_DEFICIT,
    "CCC": SignalType.CO_CHANGE_COUPLING,
    "TSA": SignalType.TS_ARCHITECTURE,
    "CXS": SignalType.COGNITIVE_COMPLEXITY,
    "FOE": SignalType.FAN_OUT_EXPLOSION,
    "CIR": SignalType.CIRCULAR_IMPORT,
    "DCA": SignalType.DEAD_CODE_ACCUMULATION,
    "MAZ": SignalType.MISSING_AUTHORIZATION,
    "ISD": SignalType.INSECURE_DEFAULT,
    "HSC": SignalType.HARDCODED_SECRET,
}

_SIGNAL_TO_ABBREV: dict[str, str] = {str(v): k for k, v in _ABBREV_TO_SIGNAL.items()}

VALID_SIGNAL_IDS = sorted(_ABBREV_TO_SIGNAL.keys())


def signal_abbrev_map() -> dict[str, str]:
    """Return stable abbreviation -> canonical signal_type mapping."""
    return {
        abbrev: str(signal_type)
        for abbrev, signal_type in sorted(_ABBREV_TO_SIGNAL.items())
    }


def resolve_signal(name: str) -> SignalType | None:
    """Resolve a signal abbreviation or full name to ``SignalType``."""
    return _resolve_signal(name)


def signal_abbrev(signal_type: str) -> str:
    """Return the short abbreviation for a signal type string."""
    return _SIGNAL_TO_ABBREV.get(str(signal_type), str(signal_type)[:3].upper())


def signal_scope_label(
    *,
    selected: list[str] | None = None,
    ignored: list[str] | None = None,
) -> str:
    """Build a compact label describing which signals contributed to a score."""
    return _signal_scope_label(selected=selected, ignored=ignored)


def build_drift_score_scope(
    *,
    context: str,
    path: str | None = None,
    signal_scope: str = "all",
    baseline_filtered: bool = False,
) -> str:
    """Return a stable scope descriptor for drift_score values."""
    return _build_drift_score_scope(
        context=context,
        path=path,
        signal_scope=signal_scope,
        baseline_filtered=baseline_filtered,
    )


def _base_response(**extra: Any) -> dict[str, Any]:
    """Build the common response envelope."""
    return {"schema_version": SCHEMA_VERSION, **extra}


# ---------------------------------------------------------------------------
# Next-step contracts (ADR-024) — machine-readable agent steering
# ---------------------------------------------------------------------------

# Predicate constants for ``done_when`` — keep in sync across endpoints.
DONE_ACCEPT_CHANGE = "accept_change == true AND blocking_reasons is empty"
DONE_SAFE_TO_COMMIT = "safe_to_commit == true"
DONE_DIFF_ACCEPT = "drift_diff.accept_change == true"
DONE_TASKS_COMPLETE = "session.tasks_remaining == 0"
DONE_NO_FINDINGS = "drift_score == 0.0 OR findings_returned == 0"
DONE_STAGED_EXISTS = "staged files exist"
DONE_TASK_AND_NUDGE = "task completed AND drift_nudge.safe_to_commit == true"
DONE_NUDGE_SAFE = "drift_nudge.safe_to_commit == true"


def _tool_call(tool: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a single tool-call descriptor for next-step contracts."""
    return {"tool": tool, "params": params or {}}


def _next_step_contract(
    *,
    next_tool: str | None,
    next_params: dict[str, Any] | None = None,
    done_when: str,
    fallback_tool: str | None = None,
    fallback_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the machine-readable next-step contract block (ADR-024).

    Returns a dict with ``next_tool_call``, ``fallback_tool_call`` and
    ``done_when`` ready to be merged into any API response.
    """
    return {
        "next_tool_call": _tool_call(next_tool, next_params) if next_tool else None,
        "fallback_tool_call": (
            _tool_call(fallback_tool, fallback_params) if fallback_tool else None
        ),
        "done_when": done_when,
    }


# ---------------------------------------------------------------------------
# Response profiles (ADR-025 Phase B) — typed handoffs
# ---------------------------------------------------------------------------

VALID_RESPONSE_PROFILES = ("planner", "coder", "verifier", "merge_readiness")

# Fields that each profile retains.  Unlisted fields are stripped.
# "schema_version", "status", "agent_instruction" are always kept.
_PROFILE_KEEP: dict[str, frozenset[str]] = {
    "planner": frozenset({
        "task_graph", "workflow_plan", "tasks", "execution_phases",
        "next_tool_call", "fallback_tool_call", "done_when",
        "drift_score", "severity", "finding_count", "top_signals",
        "scope", "guardrails", "guardrails_prompt_block",
        "risk_summary", "landscape", "trend", "warnings", "session",
    }),
    "coder": frozenset({
        "findings", "finding_count", "fix_first", "tasks",
        "drift_score", "severity", "negative_context", "items_returned",
        "next_tool_call", "fallback_tool_call", "done_when",
        "guardrails", "guardrails_prompt_block", "session",
    }),
    "verifier": frozenset({
        "drift_score", "score_delta", "safe_to_commit", "direction",
        "confidence_map", "severity", "new_findings", "resolved_findings",
        "accept_change", "blocking_reasons", "done_when",
        "next_tool_call", "fallback_tool_call", "tasks",
        "drift_detected", "resolved_count", "new_count",
        "resolved_count_by_rule", "session",
    }),
    "merge_readiness": frozenset({
        "drift_score", "severity", "score_delta", "drift_detected",
        "accept_change", "blocking_reasons", "warnings",
        "trend", "finding_count", "top_signals",
        "done_when", "session",
    }),
}

_ALWAYS_KEEP = frozenset({
    "schema_version", "status", "agent_instruction", "response_profile",
})


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


def _finding_fingerprint_value(f: Any) -> str:
    """Return deterministic fingerprint for finding-like objects used by API responses."""
    from drift.baseline import finding_fingerprint

    return finding_fingerprint(f)


def severity_rank(value: str) -> int:
    """Return numeric severity rank for cross-command comparisons."""
    return _SEVERITY_RANK.get(value, 0)


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
    from drift.output.json_output import _next_step_for_finding

    payload = finding_base_payload(f)
    payload["next_step"] = _next_step_for_finding(f)
    return payload


def _finding_detailed(f: Any, *, rank: int | None = None) -> dict[str, Any]:
    """Full finding dict for detailed responses."""
    from drift.output.json_output import (
        _expected_benefit_for_finding,
        _next_step_for_finding,
        _priority_class,
    )
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


def _trend_dict(analysis: RepoAnalysis) -> dict[str, Any] | None:
    if not analysis.trend:
        return None
    return {
        "direction": analysis.trend.direction,
        "delta": analysis.trend.delta,
        "previous_score": analysis.trend.previous_score,
    }


def _signal_weight(abbrev: str, config: Any) -> float:
    """Return the scoring weight for a signal abbreviation."""
    sig_type = _ABBREV_TO_SIGNAL.get(abbrev)
    if sig_type is None or not hasattr(config, "weights"):
        return 1.0
    return float(getattr(config.weights, str(sig_type), 1.0))


def _top_signals(
    analysis: RepoAnalysis,
    *,
    signal_filter: set[str] | None = None,
    config: Any = None,
) -> list[dict[str, Any]]:
    """Aggregate signal scores and finding counts."""
    from collections import Counter

    counts: Counter[str] = Counter()
    score_sums: dict[str, float] = {}
    for f in analysis.findings:
        abbr = signal_abbrev(f.signal_type)
        if signal_filter and abbr not in signal_filter:
            continue
        counts[abbr] += 1
        score_sums[abbr] = max(score_sums.get(abbr, 0.0), f.score)

    result = []
    for sig in counts:
        w = _signal_weight(sig, config) if config else 1.0
        result.append({
            "signal": sig,
            "score": round(score_sums[sig], 3),
            "finding_count": counts[sig],
            "weight": round(w, 4),
            "report_only": w == 0.0,
        })

    return sorted(
        result,
        key=lambda x: (-x["score"], -x["finding_count"], x["signal"]),
    )


def _fix_first_concise(analysis: RepoAnalysis, max_items: int = 5) -> list[dict[str, Any]]:
    """Build compact fix_first list (deduplicated)."""
    from drift.output.json_output import (
        _SEVERITY_RANK,
        _dedupe_findings,
        _expected_benefit_for_finding,
        _next_step_for_finding,
        _priority_class,
        _priority_rank,
    )

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


def _task_to_api_dict(t: Any) -> dict[str, Any]:
    """Convert an AgentTask to the API dict format."""
    automation_fit = t.automation_fit

    # Build canonical_refs from available positive-reference data
    canonical_refs: list[dict[str, str]] = []
    sig_abbrev = signal_abbrev(t.signal_type)

    # Source 1: canonical_exemplar from Finding metadata (e.g. PFS)
    exemplar = t.metadata.get("canonical_exemplar")
    if exemplar:
        canonical_refs.append({
            "type": "file_ref",
            "ref": str(exemplar),
            "source_signal": sig_abbrev,
        })

    # Source 2: canonical_alternative from NegativeContext items
    for nc in getattr(t, "negative_context", []):
        alt = getattr(nc, "canonical_alternative", "")
        if alt and len(canonical_refs) < 3:
            # Strip comment prefixes for clean output
            lines = alt.strip().splitlines()
            cleaned = " ".join(
                ln.lstrip("# ").strip() for ln in lines if ln.strip()
            )[:200]
            if cleaned:
                canonical_refs.append({
                    "type": "pattern",
                    "ref": cleaned,
                    "source_signal": sig_abbrev,
                })

    result = {
        "id": t.id,
        "priority": t.priority,
        "signal": sig_abbrev,
        "severity": t.severity.value,
        "title": t.title,
        "action": t.action,
        "finding_context": t.metadata.get("finding_context", "production"),
        "file": t.file_path,
        "start_line": t.start_line,
        "symbol": t.symbol,
        "logical_location": t.metadata.get("logical_location"),
        "related_files": t.related_files,
        "complexity": t.complexity,
        "automation_fit": automation_fit,
        "review_risk": t.review_risk,
        "change_scope": t.change_scope,
        "constraints": t.constraints,
        "success_criteria": t.success_criteria,
        "expected_effect": t.expected_effect,
        "depends_on": t.depends_on,
        "repair_maturity": t.repair_maturity,
        "expected_score_delta": round(t.expected_score_delta, 4),
        "batch_eligible": t.metadata.get("batch_eligible", False),
        "pattern_instance_count": t.metadata.get("pattern_instance_count", 1),
        "affected_files_for_pattern": t.metadata.get("affected_files_for_pattern", []),
        "fix_template_class": t.metadata.get("fix_template_class", ""),
        "canonical_refs": canonical_refs,
        # ADR-025 Phase A: task-graph fields
        "blocks": t.blocks,
        "batch_group": t.batch_group,
        "preferred_order": t.preferred_order,
        "parallel_with": t.parallel_with,
    }
    # ADR-025 Phase F: task contracts
    result.update(_derive_task_contract(result))
    return result


def _error_response(
    error_code: str,
    message: str,
    *,
    invalid_fields: list[dict[str, Any]] | None = None,
    suggested_fix: dict[str, Any] | None = None,
    recoverable: bool = True,
    recovery_tool_call: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a structured error response (not an exception — for tool returns)."""
    from drift.errors import ERROR_REGISTRY

    info = ERROR_REGISTRY.get(error_code)
    resp: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "type": "error",
        "error_code": error_code,
        "category": info.category if info else "input",
        "message": message,
        "invalid_fields": invalid_fields or [],
        "suggested_fix": suggested_fix,
        "recoverable": recoverable,
    }
    if recovery_tool_call is not None:
        resp["recovery_tool_call"] = recovery_tool_call
    return resp


# ---------------------------------------------------------------------------
# Task-Dependency Graph (ADR-025 Phase A)
# ---------------------------------------------------------------------------


@dataclass
class TaskGraph:
    """Topologically ordered task graph with batch groups and parallelism info."""

    tasks: list[AgentTask] = field(default_factory=list)
    batch_groups: dict[str, list[str]] = field(default_factory=dict)
    execution_phases: list[list[str]] = field(default_factory=list)
    critical_path: list[str] = field(default_factory=list)
    total_estimated_delta: float = 0.0

    def to_api_dict(self) -> dict[str, Any]:
        """Serialize graph metadata for API responses."""
        return {
            "batch_groups": self.batch_groups,
            "execution_phases": self.execution_phases,
            "critical_path": self.critical_path,
            "total_estimated_delta": round(self.total_estimated_delta, 4),
        }


def build_task_graph(tasks: list[AgentTask]) -> TaskGraph:
    """Build a dependency graph from a list of AgentTasks.

    Performs topological sort, derives batch groups from
    ``fix_template_class`` + signal, computes execution phases
    (sets of tasks runnable in parallel), and identifies the critical
    path (longest dependency chain).

    Raises ``ValueError`` on dependency cycles.
    """
    if not tasks:
        return TaskGraph()

    task_map: dict[str, AgentTask] = {t.id: t for t in tasks}
    task_ids = set(task_map)

    # --- 1. Resolve depends_on to only known tasks -----------------------
    adj: dict[str, list[str]] = defaultdict(list)  # child → parents
    children: dict[str, list[str]] = defaultdict(list)  # parent → children
    in_degree: dict[str, int] = {tid: 0 for tid in task_ids}

    for t in tasks:
        for dep in t.depends_on:
            if dep in task_ids:
                adj[t.id].append(dep)
                children[dep].append(t.id)
                in_degree[t.id] += 1

    # --- 2. Topological sort (Kahn's algorithm) --------------------------
    queue = [tid for tid, deg in in_degree.items() if deg == 0]
    sorted_ids: list[str] = []
    while queue:
        queue.sort()  # deterministic order within same level
        node = queue.pop(0)
        sorted_ids.append(node)
        for child in children[node]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if len(sorted_ids) != len(task_ids):
        visited = set(sorted_ids)
        cycle_members = [tid for tid in task_ids if tid not in visited]
        raise ValueError(
            f"Dependency cycle detected among tasks: {sorted(cycle_members)}"
        )

    # --- 3. Assign preferred_order and derive blocks ---------------------
    for idx, tid in enumerate(sorted_ids):
        t = task_map[tid]
        t.preferred_order = idx
        t.blocks = [
            c for c in children[tid] if c in task_ids
        ]

    # --- 4. Batch groups from fix_template_class + signal ----------------
    batch_groups: dict[str, list[str]] = defaultdict(list)
    for t in tasks:
        tmpl = t.metadata.get("fix_template_class", "")
        if tmpl and t.metadata.get("batch_eligible", False):
            group_key = f"{signal_abbrev(t.signal_type)}-{tmpl}"
            batch_groups[group_key].append(t.id)
            t.batch_group = group_key

    # Only keep groups with >1 member; clear batch_group on evicted tasks
    surviving = {k for k, v in batch_groups.items() if len(v) > 1}
    batch_groups = {k: v for k, v in batch_groups.items() if k in surviving}
    for t in tasks:
        if t.batch_group and t.batch_group not in surviving:
            t.batch_group = None

    # --- 5. Execution phases (level-based parallelism) -------------------
    level: dict[str, int] = {}
    for tid in sorted_ids:
        parent_levels = [level[dep] for dep in adj[tid] if dep in level]
        level[tid] = (max(parent_levels) + 1) if parent_levels else 0

    max_level = max(level.values()) if level else 0
    phases: list[list[str]] = []
    for lv in range(max_level + 1):
        phase = sorted(tid for tid, lv2 in level.items() if lv2 == lv)
        if phase:
            phases.append(phase)

    # --- 6. Parallel_with: tasks in the same phase -----------------------
    for phase in phases:
        phase_set = set(phase)
        for tid in phase:
            t = task_map[tid]
            t.parallel_with = sorted(phase_set - {tid})

    # --- 7. Critical path (longest path in DAG) --------------------------
    dist: dict[str, float] = {tid: 0.0 for tid in sorted_ids}
    pred: dict[str, str | None] = {tid: None for tid in sorted_ids}
    for tid in sorted_ids:
        for child in children[tid]:
            if child in task_ids:
                new_dist = dist[tid] + 1
                if new_dist > dist[child]:
                    dist[child] = new_dist
                    pred[child] = tid

    # Trace back from the node with max distance
    end_node = max(sorted_ids, key=lambda t: dist[t])
    critical: list[str] = []
    cur: str | None = end_node
    while cur is not None:
        critical.append(cur)
        cur = pred[cur]
    critical.reverse()

    # --- 8. Assemble TaskGraph -------------------------------------------
    sorted_tasks = [task_map[tid] for tid in sorted_ids]
    total_delta = sum(t.expected_score_delta for t in sorted_tasks)

    return TaskGraph(
        tasks=sorted_tasks,
        batch_groups=dict(batch_groups),
        execution_phases=phases,
        critical_path=critical,
        total_estimated_delta=total_delta,
    )


# ---------------------------------------------------------------------------
# Workflow plans (ADR-025 Phase C) — executable repair choreography
# ---------------------------------------------------------------------------


@dataclass
class WorkflowStep:
    """One step in an executable workflow plan."""

    step: int
    label: str
    tool: str
    params: dict[str, Any] = field(default_factory=dict)
    preconditions: list[str] = field(default_factory=list)
    task_ids: list[str] = field(default_factory=list)
    parallel: bool = False
    abort_if: str = ""

    def to_api_dict(self) -> dict[str, Any]:
        """Serialise to API response dict."""
        return {
            "step": self.step,
            "label": self.label,
            "tool": self.tool,
            "params": self.params,
            "preconditions": self.preconditions,
            "task_ids": self.task_ids,
            "parallel": self.parallel,
            "abort_if": self.abort_if,
        }


@dataclass
class WorkflowPlan:
    """First-class executable plan built from a task graph."""

    steps: list[WorkflowStep] = field(default_factory=list)
    success_criteria: str = ""
    abort_criteria: str = ""
    estimated_score_delta: float = 0.0

    # -- Phase E: Plan-Invalidierung (ADR-025) -------------------------------
    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = field(default_factory=lambda: __import__("time").time())
    depended_on_repo_state: dict[str, Any] = field(default_factory=dict)
    plan_fingerprint: str = ""
    invalidation_triggers: list[str] = field(default_factory=list)
    invalidated: bool = False
    invalidation_reason: str = ""

    def to_api_dict(self) -> dict[str, Any]:
        """Serialise to API response dict."""
        return {
            "steps": [s.to_api_dict() for s in self.steps],
            "success_criteria": self.success_criteria,
            "abort_criteria": self.abort_criteria,
            "estimated_score_delta": round(self.estimated_score_delta, 4),
            "plan_id": self.plan_id,
            "created_at": self.created_at,
            "depended_on_repo_state": self.depended_on_repo_state,
            "plan_fingerprint": self.plan_fingerprint,
            "invalidated": self.invalidated,
            "invalidation_reason": self.invalidation_reason,
        }


def build_workflow_plan(
    graph: TaskGraph,
    *,
    session_id: str = "",
    repo_path: str = ".",
) -> WorkflowPlan:
    """Build an executable workflow plan from a task graph.

    Converts execution phases into ordered steps with tool calls,
    preconditions, and abort criteria that an agent can follow
    sequentially.
    """
    steps: list[WorkflowStep] = []
    step_num = 1

    for phase_idx, phase_ids in enumerate(graph.execution_phases):
        batch_ids = [
            tid for tid in phase_ids
            if any(tid in members for members in graph.batch_groups.values())
        ]
        solo_ids = [tid for tid in phase_ids if tid not in batch_ids]

        # Batch-eligible tasks in one step
        if batch_ids:
            params: dict[str, Any] = {"path": repo_path}
            if session_id:
                params["session_id"] = session_id
            steps.append(WorkflowStep(
                step=step_num,
                label=f"Phase {phase_idx + 1}: batch-fix {len(batch_ids)} tasks",
                tool="drift_fix_plan",
                params=params,
                preconditions=(
                    [f"phase {phase_idx} completed"]
                    if phase_idx > 0 else []
                ),
                task_ids=sorted(batch_ids),
                parallel=True,
                abort_if="drift_nudge.direction == 'degrading'",
            ))
            step_num += 1

        # Solo tasks
        for tid in sorted(solo_ids):
            params = {"path": repo_path}
            if session_id:
                params["session_id"] = session_id
            steps.append(WorkflowStep(
                step=step_num,
                label=f"Fix task {tid}",
                tool="drift_fix_plan",
                params=params,
                preconditions=(
                    [f"phase {phase_idx} dependencies resolved"]
                    if phase_idx > 0 else []
                ),
                task_ids=[tid],
                parallel=False,
                abort_if="drift_nudge.direction == 'degrading'",
            ))
            step_num += 1

    # Verification step
    verify_params: dict[str, Any] = {"path": repo_path, "uncommitted": True}
    if session_id:
        verify_params["session_id"] = session_id
    steps.append(WorkflowStep(
        step=step_num,
        label="Verify: nudge check",
        tool="drift_nudge",
        params=verify_params,
        preconditions=["all fix steps completed"],
        task_ids=[],
        parallel=False,
        abort_if="",
    ))

    plan = WorkflowPlan(
        steps=steps,
        success_criteria=DONE_SAFE_TO_COMMIT,
        abort_criteria="drift_nudge.direction == 'degrading' for 2 consecutive nudges",
        estimated_score_delta=graph.total_estimated_delta,
    )

    # Phase E: capture repo state and compute fingerprint
    repo_state = _capture_repo_state(repo_path, graph)
    plan.depended_on_repo_state = repo_state
    plan.plan_fingerprint = _compute_plan_fingerprint(plan)
    plan.invalidation_triggers = [
        "head_commit_changed",
        "branch_changed",
        "affected_file_modified",
        "dependent_task_failed",
        "consecutive_degrading_nudges",
    ]
    return plan


# ---------------------------------------------------------------------------
# Plan-Invalidierung (ADR-025 Phase E)
# ---------------------------------------------------------------------------

_DEFAULT_INVALIDATION_TRIGGERS = frozenset({
    "head_commit_changed",
    "branch_changed",
    "affected_file_modified",
    "dependent_task_failed",
    "consecutive_degrading_nudges",
})


def _git_cmd(repo_path: str, *args: str) -> str:
    """Run a git command and return stripped stdout, or '' on failure."""
    try:
        result = subprocess.run(  # noqa: S603, S607
            ["git", *args],
            cwd=repo_path,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _capture_repo_state(
    repo_path: str,
    graph: TaskGraph,
) -> dict[str, Any]:
    """Snapshot the repo state that this plan depends on."""
    head_commit = _git_cmd(repo_path, "rev-parse", "HEAD")
    branch = _git_cmd(repo_path, "rev-parse", "--abbrev-ref", "HEAD")
    dirty_output = _git_cmd(repo_path, "diff", "--name-only")
    dirty_files = sorted(dirty_output.splitlines()) if dirty_output else []

    # Collect all files referenced by tasks in the graph
    affected: set[str] = set()
    for task in graph.tasks:
        if task.file_path:
            affected.add(task.file_path)
        affected.update(task.related_files)

    affected_sorted = sorted(affected)
    files_hash = hashlib.sha256(
        "|".join(affected_sorted).encode()
    ).hexdigest()[:16]

    return {
        "head_commit": head_commit,
        "branch": branch,
        "affected_files": affected_sorted,
        "affected_files_hash": files_hash,
        "dirty_files": dirty_files,
    }


def _compute_plan_fingerprint(plan: WorkflowPlan) -> str:
    """Compute a SHA-256 fingerprint over plan structure and repo state."""
    import json as _json

    parts = [
        _json.dumps([s.to_api_dict() for s in plan.steps], sort_keys=True),
        _json.dumps(plan.depended_on_repo_state, sort_keys=True),
        plan.success_criteria,
        plan.abort_criteria,
    ]
    combined = "\n".join(parts)
    return hashlib.sha256(combined.encode()).hexdigest()


@dataclass
class PlanValidationResult:
    """Result of validating a workflow plan against current repo state."""

    valid: bool
    reason: str
    stale_files: list[str] = field(default_factory=list)
    recommendation: str = "continue"  # "continue" | "re_plan" | "abort"
    triggered: list[str] = field(default_factory=list)

    def to_api_dict(self) -> dict[str, Any]:
        """Serialise for API responses."""
        return {
            "valid": self.valid,
            "reason": self.reason,
            "stale_files": self.stale_files,
            "recommendation": self.recommendation,
            "triggered": self.triggered,
        }


def validate_plan(
    plan: WorkflowPlan,
    repo_path: str,
) -> PlanValidationResult:
    """Validate whether a workflow plan is still valid against current repo state.

    Compares the stored ``depended_on_repo_state`` against the live repo.
    Returns a ``PlanValidationResult`` with recommendation.
    """
    if plan.invalidated:
        return PlanValidationResult(
            valid=False,
            reason=plan.invalidation_reason or "plan explicitly invalidated",
            recommendation="re_plan",
            triggered=["explicit_invalidation"],
        )

    state = plan.depended_on_repo_state
    if not state:
        # Legacy plan without repo state — cannot validate, assume ok
        return PlanValidationResult(
            valid=True,
            reason="legacy_plan_no_state",
            recommendation="continue",
        )

    triggered: list[str] = []
    stale_files: list[str] = []

    # Check HEAD commit
    current_head = _git_cmd(repo_path, "rev-parse", "HEAD")
    if state.get("head_commit") and current_head != state["head_commit"]:
        triggered.append("head_commit_changed")

    # Check branch
    current_branch = _git_cmd(repo_path, "rev-parse", "--abbrev-ref", "HEAD")
    if state.get("branch") and current_branch != state["branch"]:
        triggered.append("branch_changed")

    # Check affected files
    affected = state.get("affected_files", [])
    if affected:
        current_dirty = _git_cmd(repo_path, "diff", "--name-only")
        current_dirty_set = set(current_dirty.splitlines()) if current_dirty else set()
        for fpath in affected:
            if fpath in current_dirty_set:
                stale_files.append(fpath)
        if stale_files:
            triggered.append("affected_file_modified")

    if not triggered:
        return PlanValidationResult(
            valid=True,
            reason="repo_state_unchanged",
            recommendation="continue",
        )

    # Determine severity
    hard_triggers = {"head_commit_changed", "branch_changed"}
    if hard_triggers & set(triggered):
        return PlanValidationResult(
            valid=False,
            reason=f"repo state changed: {', '.join(triggered)}",
            stale_files=stale_files,
            recommendation="re_plan",
            triggered=triggered,
        )

    return PlanValidationResult(
        valid=False,
        reason=f"affected files modified: {', '.join(stale_files)}",
        stale_files=stale_files,
        recommendation="re_plan",
        triggered=triggered,
    )


# ---------------------------------------------------------------------------
# Task contracts (ADR-025 Phase F)
# ---------------------------------------------------------------------------


def _derive_task_contract(task_dict: dict[str, Any]) -> dict[str, Any]:
    """Derive machine-checkable contract fields from a task dict.

    Returns additional fields to merge into the task API output.
    """
    # allowed_files: primary file + related files
    allowed: list[str] = []
    primary = task_dict.get("file", "")
    if primary:
        allowed.append(primary)
    related = task_dict.get("related_files", [])
    allowed.extend(r for r in related if r not in allowed)

    return {
        "allowed_files": allowed,
        "completion_evidence": {
            "type": "nudge_safe",
            "tool": "drift_nudge",
            "predicate": "safe_to_commit == true",
        },
    }

"""Task-dependency graph, workflow plans, and plan validation (ADR-025).

Provides the full task-graph lifecycle: dependency ordering, batch grouping,
execution-phase computation, executable workflow-plan construction, and
plan-invalidation checks against live repository state.
"""

from __future__ import annotations

import hashlib
import subprocess
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from drift.next_step_contract import DONE_SAFE_TO_COMMIT
from drift.signal_mapping import signal_abbrev

if TYPE_CHECKING:
    from drift.models import AgentTask


def _task_to_api_dict(t: Any) -> dict[str, Any]:
    """Convert an AgentTask to the API dict format."""
    automation_fit = t.automation_fit

    # Build canonical_refs from available positive-reference data
    canonical_refs: list[dict[str, str]] = []
    sig_abbrev = signal_abbrev(t.signal_type)

    # Source 1: canonical_exemplar from Finding metadata (e.g. PFS)
    exemplar = t.metadata.get("canonical_exemplar")
    if exemplar:
        canonical_refs.append(
            {
                "type": "file_ref",
                "ref": str(exemplar),
                "source_signal": sig_abbrev,
            }
        )

    # Source 2: canonical_alternative from NegativeContext items
    for nc in getattr(t, "negative_context", []):
        alt = getattr(nc, "canonical_alternative", "")
        if alt and len(canonical_refs) < 3:
            # Strip comment prefixes for clean output
            lines = alt.strip().splitlines()
            cleaned = " ".join(ln.lstrip("# ").strip() for ln in lines if ln.strip())[:200]
            if cleaned:
                canonical_refs.append(
                    {
                        "type": "pattern",
                        "ref": cleaned,
                        "source_signal": sig_abbrev,
                    }
                )

    result = {
        "id": t.id,
        "priority": t.priority,
        "signal": sig_abbrev,
        "signal_abbrev": sig_abbrev,
        "severity": t.severity.value,
        "title": t.title,
        "action": t.action,
        "finding_context": t.metadata.get("finding_context", "production"),
        "file": t.file_path,
        "start_line": t.start_line,
        "symbol": t.symbol,
        "related_files": t.related_files,
        "complexity": t.complexity,
        "automation_fit": automation_fit,
        "automation_fitness": automation_fit,
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

    task_map: dict[str, AgentTask] = {task.id: task for task in tasks}
    task_ids = set(task_map)
    adj, children, in_degree = _task_graph_dependencies(tasks, task_ids)
    sorted_ids = _task_graph_topological_sort(task_ids, children, in_degree)

    _task_graph_assign_order_and_blocks(sorted_ids, task_map, children, task_ids)
    batch_groups = _task_graph_batch_groups(tasks)
    phases = _task_graph_execution_phases(sorted_ids, adj)
    _task_graph_parallel_with(phases, task_map)
    critical = _task_graph_critical_path(sorted_ids, children, task_ids)

    sorted_tasks = [task_map[task_id] for task_id in sorted_ids]
    total_delta = sum(task.expected_score_delta for task in sorted_tasks)

    return TaskGraph(
        tasks=sorted_tasks,
        batch_groups=dict(batch_groups),
        execution_phases=phases,
        critical_path=critical,
        total_estimated_delta=total_delta,
    )


def _task_graph_dependencies(
    tasks: list[AgentTask],
    task_ids: set[str],
) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, int]]:
    """Build dependency maps for task graph construction."""
    adj: dict[str, list[str]] = defaultdict(list)
    children: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {task_id: 0 for task_id in task_ids}

    for task in tasks:
        for dep in task.depends_on:
            if dep in task_ids:
                adj[task.id].append(dep)
                children[dep].append(task.id)
                in_degree[task.id] += 1
    return adj, children, in_degree


def _task_graph_topological_sort(
    task_ids: set[str],
    children: dict[str, list[str]],
    in_degree: dict[str, int],
) -> list[str]:
    """Return deterministic topological order for tasks."""
    queue = [task_id for task_id, degree in in_degree.items() if degree == 0]
    sorted_ids: list[str] = []
    while queue:
        queue.sort()
        node = queue.pop(0)
        sorted_ids.append(node)
        for child in children[node]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if len(sorted_ids) != len(task_ids):
        visited = set(sorted_ids)
        cycle_members = [task_id for task_id in task_ids if task_id not in visited]
        raise ValueError(f"Dependency cycle detected among tasks: {sorted(cycle_members)}")
    return sorted_ids


def _task_graph_assign_order_and_blocks(
    sorted_ids: list[str],
    task_map: dict[str, AgentTask],
    children: dict[str, list[str]],
    task_ids: set[str],
) -> None:
    """Assign stable order and blocking relationships to tasks."""
    for index, task_id in enumerate(sorted_ids):
        task = task_map[task_id]
        task.preferred_order = index
        task.blocks = [child for child in children[task_id] if child in task_ids]


def _task_graph_batch_groups(tasks: list[AgentTask]) -> dict[str, list[str]]:
    """Build surviving batch groups and annotate task.batch_group."""
    batch_groups: dict[str, list[str]] = defaultdict(list)
    for task in tasks:
        tmpl = task.metadata.get("fix_template_class", "")
        if tmpl and task.metadata.get("batch_eligible", False):
            group_key = f"{signal_abbrev(task.signal_type)}-{tmpl}"
            batch_groups[group_key].append(task.id)
            task.batch_group = group_key

    surviving = {key for key, members in batch_groups.items() if len(members) > 1}
    filtered = {key: members for key, members in batch_groups.items() if key in surviving}
    for task in tasks:
        if task.batch_group and task.batch_group not in surviving:
            task.batch_group = None
    return filtered


def _task_graph_execution_phases(
    sorted_ids: list[str],
    adj: dict[str, list[str]],
) -> list[list[str]]:
    """Compute level-based execution phases from dependency edges."""
    level: dict[str, int] = {}
    for task_id in sorted_ids:
        parent_levels = [level[dep] for dep in adj[task_id] if dep in level]
        level[task_id] = (max(parent_levels) + 1) if parent_levels else 0

    max_level = max(level.values()) if level else 0
    phases: list[list[str]] = []
    for current_level in range(max_level + 1):
        phase = sorted(
            task_id for task_id, level_value in level.items() if level_value == current_level
        )
        if phase:
            phases.append(phase)
    return phases


def _task_graph_parallel_with(
    phases: list[list[str]],
    task_map: dict[str, AgentTask],
) -> None:
    """Populate parallel_with for tasks inside each phase."""
    for phase in phases:
        phase_set = set(phase)
        for task_id in phase:
            task = task_map[task_id]
            task.parallel_with = sorted(phase_set - {task_id})


def _task_graph_critical_path(
    sorted_ids: list[str],
    children: dict[str, list[str]],
    task_ids: set[str],
) -> list[str]:
    """Compute the longest dependency path in the DAG."""
    dist: dict[str, float] = {task_id: 0.0 for task_id in sorted_ids}
    pred: dict[str, str | None] = {task_id: None for task_id in sorted_ids}
    for task_id in sorted_ids:
        for child in children[task_id]:
            if child in task_ids:
                new_dist = dist[task_id] + 1
                if new_dist > dist[child]:
                    dist[child] = new_dist
                    pred[child] = task_id

    end_node = max(sorted_ids, key=lambda task_id: dist[task_id])
    critical: list[str] = []
    current: str | None = end_node
    while current is not None:
        critical.append(current)
        current = pred[current]
    critical.reverse()
    return critical


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
            tid
            for tid in phase_ids
            if any(tid in members for members in graph.batch_groups.values())
        ]
        solo_ids = [tid for tid in phase_ids if tid not in batch_ids]

        # Batch-eligible tasks in one step
        if batch_ids:
            params: dict[str, Any] = {"path": repo_path}
            if session_id:
                params["session_id"] = session_id
            steps.append(
                WorkflowStep(
                    step=step_num,
                    label=f"Phase {phase_idx + 1}: batch-fix {len(batch_ids)} tasks",
                    tool="drift_fix_plan",
                    params=params,
                    preconditions=([f"phase {phase_idx} completed"] if phase_idx > 0 else []),
                    task_ids=sorted(batch_ids),
                    parallel=True,
                    abort_if="drift_nudge.direction == 'degrading'",
                )
            )
            step_num += 1

        # Solo tasks
        for tid in sorted(solo_ids):
            params = {"path": repo_path}
            if session_id:
                params["session_id"] = session_id
            steps.append(
                WorkflowStep(
                    step=step_num,
                    label=f"Fix task {tid}",
                    tool="drift_fix_plan",
                    params=params,
                    preconditions=(
                        [f"phase {phase_idx} dependencies resolved"] if phase_idx > 0 else []
                    ),
                    task_ids=[tid],
                    parallel=False,
                    abort_if="drift_nudge.direction == 'degrading'",
                )
            )
            step_num += 1

    # Verification step
    verify_params: dict[str, Any] = {"path": repo_path, "uncommitted": True}
    if session_id:
        verify_params["session_id"] = session_id
    steps.append(
        WorkflowStep(
            step=step_num,
            label="Verify: nudge check",
            tool="drift_nudge",
            params=verify_params,
            preconditions=["all fix steps completed"],
            task_ids=[],
            parallel=False,
            abort_if="",
        )
    )

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

_DEFAULT_INVALIDATION_TRIGGERS = frozenset(
    {
        "head_commit_changed",
        "branch_changed",
        "affected_file_modified",
        "dependent_task_failed",
        "consecutive_degrading_nudges",
    }
)


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
    files_hash = hashlib.sha256("|".join(affected_sorted).encode()).hexdigest()[:16]

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

# Files that agents must never modify directly
_FORBIDDEN_FILES_DEFAULT: frozenset[str] = frozenset(
    {
        "POLICY.md",
        "pyproject.toml",
        "uv.lock",
    }
)

_FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "audit_results/",
    ".github/",
)


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

    # forbidden_files: policy-protected paths
    forbidden: list[str] = sorted(_FORBIDDEN_FILES_DEFAULT)

    # completion_evidence: derive from signal type
    evidence_type = "nudge_safe"
    evidence_tool = "drift_nudge"
    evidence_predicate = "safe_to_commit == true"

    # required_audit_artifacts: only if signal is under signals/
    signal = task_dict.get("signal", "")
    required_audit: list[str] = []
    if signal:
        # Signals that modify src/drift/signals/ require audit artifacts
        required_audit = []  # filled by caller if needed

    return {
        "allowed_files": allowed,
        "forbidden_files": forbidden,
        "completion_evidence": {
            "type": evidence_type,
            "tool": evidence_tool,
            "predicate": evidence_predicate,
        },
        "required_audit_artifacts": required_audit,
        "max_files_changed": max(len(allowed) + 2, 3),
    }

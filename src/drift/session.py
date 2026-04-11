"""MCP session management for stateful multi-step agent workflows.

Provides:

* ``DriftSession`` — in-memory session holding scope, baseline state,
  fix-plan queue, and guardrails across MCP tool calls.
* ``SessionManager`` — singleton that manages active sessions with
  TTL-based expiry and optional disk persistence.

Sessions complement the ``BaselineManager`` (ADR-020) — baselines handle
analysis-level persistence while sessions handle orchestration-level state.
The API layer (``drift.api``) remains stateless.

Architectural invariant (Phase-5 boundary contract):
    session.py   → stateful, multi-call orchestration context
    pipeline.py  → stateless, single-run transformation graph

Decision: ADR-022
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

logger = logging.getLogger("drift")

_SCHEMA_VERSION = "1.0"
_DEFAULT_TTL_SECONDS = 1800  # 30 minutes
_DEFAULT_EFFECTIVENESS_THRESHOLDS: dict[str, float] = {
    "low_effect_resolved_per_changed_file": 0.25,
    "low_effect_resolved_per_100_loc_changed": 0.5,
    "high_churn_min_changed_files": 5,
    "high_churn_min_loc_changed": 200,
}


@dataclass
class OrchestrationMetrics:
    """Tracks orchestration-level metrics for a session (ADR-025 Phase G)."""

    # -- Efficiency ----------------------------------------------------------
    plans_created: int = 0
    plans_invalidated: int = 0
    replan_reasons: list[str] = field(default_factory=list)
    tasks_claimed: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_released: int = 0
    tasks_expired: int = 0
    duplicate_claims_attempted: int = 0

    # -- Time efficiency -----------------------------------------------------
    first_claim_at: float | None = None
    first_completion_at: float | None = None
    last_completion_at: float | None = None
    total_lease_time_seconds: float = 0.0

    # -- Quality -------------------------------------------------------------
    nudge_checks: int = 0
    nudge_improving: int = 0
    nudge_degrading: int = 0
    nudge_stable: int = 0
    verification_failures: int = 0

    # -- Quality proxy counters ---------------------------------------------
    total_findings_seen: int = 0
    findings_suppressed: int = 0
    findings_acted_on: int = 0

    # -- Outcome-centric effectiveness KPIs --------------------------------
    verification_runs: int = 0
    changed_files_total: int = 0
    loc_changed_total: int = 0
    resolved_findings_total: int = 0
    new_findings_total: int = 0
    relocated_findings_total: int = 0

    def record_verification(
        self,
        *,
        changed_file_count: int,
        loc_changed: int,
        resolved_count: int,
        new_finding_count: int,
    ) -> None:
        """Record a verification run for outcome-centric effectiveness tracking."""
        self.verification_runs += 1
        self.changed_files_total += max(0, changed_file_count)
        self.loc_changed_total += max(0, loc_changed)
        self.resolved_findings_total += max(0, resolved_count)
        self.new_findings_total += max(0, new_finding_count)
        self.relocated_findings_total += max(0, min(resolved_count, new_finding_count))

    def to_dict(self) -> dict[str, Any]:
        """Serialise metrics to a dict."""
        completed = self.tasks_completed
        claimed = self.tasks_claimed
        failed = self.tasks_failed
        expired = self.tasks_expired

        discarded_ratio = (
            (failed + expired) / claimed if claimed > 0 else 0.0
        )
        plan_reuse = (
            completed / max(self.plans_created, 1)
            if self.plans_created > 0
            else 0.0
        )

        return {
            "plans_created": self.plans_created,
            "plans_invalidated": self.plans_invalidated,
            "replan_reasons": self.replan_reasons,
            "tasks_claimed": claimed,
            "tasks_completed": completed,
            "tasks_failed": failed,
            "tasks_released": self.tasks_released,
            "tasks_expired": expired,
            "duplicate_claims_attempted": self.duplicate_claims_attempted,
            "first_claim_at": self.first_claim_at,
            "first_completion_at": self.first_completion_at,
            "last_completion_at": self.last_completion_at,
            "total_lease_time_seconds": round(self.total_lease_time_seconds, 2),
            "nudge_checks": self.nudge_checks,
            "nudge_improving": self.nudge_improving,
            "nudge_degrading": self.nudge_degrading,
            "nudge_stable": self.nudge_stable,
            "verification_failures": self.verification_failures,
            "total_findings_seen": self.total_findings_seen,
            "findings_suppressed": self.findings_suppressed,
            "findings_acted_on": self.findings_acted_on,
            "suppression_ratio": round(
                (self.findings_suppressed / self.total_findings_seen)
                if self.total_findings_seen > 0
                else 0.0,
                4,
            ),
            "action_ratio": round(
                (
                    self.findings_acted_on
                    / max(self.total_findings_seen - self.findings_suppressed, 1)
                )
                if self.total_findings_seen > 0
                else 0.0,
                4,
            ),
            "verification_runs": self.verification_runs,
            "changed_files_total": self.changed_files_total,
            "loc_changed_total": self.loc_changed_total,
            "resolved_findings_total": self.resolved_findings_total,
            "new_findings_total": self.new_findings_total,
            "relocated_findings_total": self.relocated_findings_total,
            "resolved_findings_per_changed_file": round(
                self.resolved_findings_total / self.changed_files_total
                if self.changed_files_total > 0
                else 0.0,
                4,
            ),
            "resolved_findings_per_100_loc_changed": round(
                (self.resolved_findings_total * 100.0) / self.loc_changed_total
                if self.loc_changed_total > 0
                else 0.0,
                4,
            ),
            "relocated_findings_ratio": round(
                self.relocated_findings_total / self.resolved_findings_total
                if self.resolved_findings_total > 0
                else 0.0,
                4,
            ),
            "verification_density": round(
                self.verification_runs / self.changed_files_total
                if self.changed_files_total > 0
                else 0.0,
                4,
            ),
            "discarded_work_ratio": round(discarded_ratio, 4),
            "plan_reuse_ratio": round(plan_reuse, 4),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OrchestrationMetrics:
        """Deserialise metrics from a dict."""
        return cls(
            plans_created=data.get("plans_created", 0),
            plans_invalidated=data.get("plans_invalidated", 0),
            replan_reasons=data.get("replan_reasons", []),
            tasks_claimed=data.get("tasks_claimed", 0),
            tasks_completed=data.get("tasks_completed", 0),
            tasks_failed=data.get("tasks_failed", 0),
            tasks_released=data.get("tasks_released", 0),
            tasks_expired=data.get("tasks_expired", 0),
            duplicate_claims_attempted=data.get("duplicate_claims_attempted", 0),
            first_claim_at=data.get("first_claim_at"),
            first_completion_at=data.get("first_completion_at"),
            last_completion_at=data.get("last_completion_at"),
            total_lease_time_seconds=data.get("total_lease_time_seconds", 0.0),
            nudge_checks=data.get("nudge_checks", 0),
            nudge_improving=data.get("nudge_improving", 0),
            nudge_degrading=data.get("nudge_degrading", 0),
            nudge_stable=data.get("nudge_stable", 0),
            verification_failures=data.get("verification_failures", 0),
            total_findings_seen=data.get("total_findings_seen", 0),
            findings_suppressed=data.get("findings_suppressed", 0),
            findings_acted_on=data.get("findings_acted_on", 0),
            verification_runs=data.get("verification_runs", 0),
            changed_files_total=data.get("changed_files_total", 0),
            loc_changed_total=data.get("loc_changed_total", 0),
            resolved_findings_total=data.get("resolved_findings_total", 0),
            new_findings_total=data.get("new_findings_total", 0),
            relocated_findings_total=data.get("relocated_findings_total", 0),
        )


@dataclass
class DriftSession:
    """In-memory session for a multi-step MCP workflow.

    Tracks active scope, last scan results, fix-plan task queue,
    and brief guardrails so agents can resume work without repeating
    parameters or re-scanning.
    """

    session_id: str
    repo_path: str
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    ttl_seconds: int = _DEFAULT_TTL_SECONDS

    # -- Scope defaults (used as fallback for tool params) -------------------
    signals: list[str] | None = None
    exclude_signals: list[str] | None = None
    target_path: str | None = None
    exclude_paths: list[str] | None = None

    # -- Scan state ----------------------------------------------------------
    last_scan_score: float | None = None
    last_scan_top_signals: list[dict[str, Any]] | None = None
    last_scan_finding_count: int | None = None
    baseline_file: str | None = None
    score_at_start: float | None = None

    # -- Fix-plan state ------------------------------------------------------
    selected_tasks: list[dict[str, Any]] | None = None
    completed_task_ids: list[str] = field(default_factory=list)

    # -- Task-queue leasing --------------------------------------------------
    active_leases: dict[str, dict[str, Any]] = field(default_factory=dict)
    failed_task_ids: list[str] = field(default_factory=list)
    task_reclaim_counts: dict[str, int] = field(default_factory=dict)
    completed_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    _lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False, compare=False
    )

    # -- Brief state ---------------------------------------------------------
    guardrails: list[dict[str, Any]] | None = None
    guardrails_prompt_block: str | None = None

    # -- Counters / Metrics --------------------------------------------------
    tool_calls: int = 0
    metrics: OrchestrationMetrics = field(default_factory=OrchestrationMetrics)

    # -- Timing instrumentation (WP-4) --------------------------------------
    _last_call_begin: float | None = field(default=None, init=False, repr=False)
    _last_touch_ts: float | None = field(default=None, init=False, repr=False)
    _total_tool_ms: float = field(default=0.0, init=False, repr=False)
    _total_inter_call_ms: float = field(default=0.0, init=False, repr=False)
    _seen_verification_payload_hashes: set[str] = field(
        default_factory=set, init=False, repr=False
    )

    # -- Agent effectiveness / workflow state -------------------------------
    phase: str = "init"
    trace: list[dict[str, Any]] = field(default_factory=list)
    run_history: list[dict[str, Any]] = field(default_factory=list)
    effectiveness_thresholds: dict[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_EFFECTIVENESS_THRESHOLDS)
    )
    diagnostic_hypotheses: dict[str, dict[str, Any]] = field(default_factory=dict)
    git_head_at_plan: str | None = None

    # -- queries -------------------------------------------------------------

    def is_valid(self) -> bool:
        """Return ``True`` if the session has not expired."""
        return (time.time() - self.last_activity) < self.ttl_seconds

    def touch(self) -> None:
        """Update last activity timestamp and increment tool call counter."""
        now = time.time()
        # Record tool execution time: now (end) - begin_call time
        if self._last_call_begin is not None:
            tool_ms = (now - self._last_call_begin) * 1000
            self._total_tool_ms += tool_ms
        self._last_call_begin = None
        self._last_touch_ts = now
        self.last_activity = now
        self.tool_calls += 1

    def begin_call(self) -> None:
        """Record the start of a tool call for timing decomposition."""
        now = time.time()
        # Gap between end of previous call and start of this call = agent time
        if self._last_touch_ts is not None:
            gap_ms = (now - self._last_touch_ts) * 1000
            self._total_inter_call_ms += gap_ms
        self._last_call_begin = now

    def tasks_remaining(self) -> int:
        """Return the number of pending tasks (excluding completed and failed)."""
        if not self.selected_tasks:
            return 0
        excluded = set(self.completed_task_ids) | set(self.failed_task_ids)
        return sum(
            1
            for t in self.selected_tasks
            if t.get("id", t.get("task_id", "")) not in excluded
        )

    def scope_label(self) -> str:
        """Return a human-readable scope description."""
        parts: list[str] = []
        if self.signals:
            parts.append(f"signals={','.join(self.signals)}")
        if self.exclude_signals:
            parts.append(f"exclude={','.join(self.exclude_signals)}")
        if self.target_path:
            parts.append(f"path={self.target_path}")
        return "; ".join(parts) if parts else "all"

    def advance_phase(self, new_phase: str) -> str:
        """Advance to a new workflow phase and return the previous phase."""
        old = self.phase
        self.phase = new_phase
        return old

    def record_trace(
        self,
        tool: str,
        advisory: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Append one trace entry for chronological workflow diagnostics."""
        entry: dict[str, Any] = {
            "tool": tool,
            "ts": time.time(),
            "phase": self.phase,
            "advisory": advisory,
            "tool_calls_so_far": self.tool_calls,
        }
        if metadata:
            entry.update(metadata)
        self.trace.append(entry)

    def snapshot_run(self, score: float, finding_count: int) -> None:
        """Record a score/finding snapshot for trend-aware session guidance."""
        self.run_history.append(
            {
                "score": score,
                "finding_count": finding_count,
                "ts": time.time(),
                "tool_calls_at": self.tool_calls,
            }
        )

    def register_diagnostic_hypothesis(self, hypothesis_id: str, payload: dict[str, Any]) -> None:
        """Store diagnostic hypothesis payload by ID for later trace linkage."""
        self.diagnostic_hypotheses[hypothesis_id] = dict(payload)

    def get_diagnostic_hypothesis(self, hypothesis_id: str) -> dict[str, Any] | None:
        """Fetch a previously registered diagnostic hypothesis by ID."""
        value = self.diagnostic_hypotheses.get(hypothesis_id)
        if isinstance(value, dict):
            return value
        return None

    def consecutive_nudge_degradations(self) -> int:
        """Return count of consecutive degrading drift_nudge entries from trace tail."""
        count = 0
        for entry in reversed(self.trace):
            if not isinstance(entry, dict) or entry.get("tool") != "drift_nudge":
                continue
            if entry.get("direction") == "degrading":
                count += 1
                continue
            break
        return count

    def plan_stale_count(self) -> int:
        """Return number of trace entries flagged with plan_stale=True."""
        return sum(
            1
            for entry in self.trace
            if isinstance(entry, dict)
            and entry.get("tool") == "drift_fix_plan"
            and bool(entry.get("plan_stale"))
        )

    def _effectiveness_warnings(self) -> list[dict[str, Any]]:
        """Return deterministic warning objects from effectiveness KPIs."""
        m = self.metrics
        thresholds = {
            **_DEFAULT_EFFECTIVENESS_THRESHOLDS,
            **(self.effectiveness_thresholds or {}),
        }
        resolved_per_file = (
            m.resolved_findings_total / m.changed_files_total
            if m.changed_files_total > 0
            else 0.0
        )
        resolved_per_100_loc = (
            (m.resolved_findings_total * 100.0) / m.loc_changed_total
            if m.loc_changed_total > 0
            else 0.0
        )

        warnings: list[dict[str, Any]] = []
        if (
            m.changed_files_total >= int(thresholds["high_churn_min_changed_files"])
            and m.loc_changed_total >= int(thresholds["high_churn_min_loc_changed"])
            and (
                resolved_per_file
                < float(thresholds["low_effect_resolved_per_changed_file"])
                or resolved_per_100_loc
                < float(thresholds["low_effect_resolved_per_100_loc_changed"])
            )
        ):
            warnings.append(
                {
                    "code": "low_effect_high_churn",
                    "message": (
                        "Low resolved-finding yield despite high churn; narrow scope "
                        "before continuing broad edits."
                    ),
                }
            )
        return warnings

    def summary(self) -> dict[str, Any]:
        """Return a compact session summary for status responses."""
        now = time.time()
        return {
            "session_id": self.session_id,
            "valid": self.is_valid(),
            "repo_path": self.repo_path,
            "scope": self.scope_label(),
            "phase": self.phase,
            "trace_entries": len(self.trace),
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "ttl_remaining_seconds": max(
                0.0, self.ttl_seconds - (now - self.last_activity)
            ),
            "tool_calls": self.tool_calls,
            "last_scan": {
                "score": self.last_scan_score,
                "top_signals": self.last_scan_top_signals,
                "finding_count": self.last_scan_finding_count,
            }
            if self.last_scan_score is not None
            else None,
            "task_queue": {
                "total": len(self.selected_tasks) if self.selected_tasks else 0,
                "completed": len(self.completed_task_ids),
                "claimed": len(self.active_leases),
                "failed": len(self.failed_task_ids),
                "remaining": self.tasks_remaining(),
            },
            "guardrails_active": self.guardrails is not None,
            "baseline_file": self.baseline_file,
            "score_at_start": self.score_at_start,
            "orchestration_metrics": self.metrics.to_dict(),
            "effectiveness_warnings": self._effectiveness_warnings(),
        }

    def end_summary(self) -> dict[str, Any]:
        """Return a final summary when the session ends."""
        now = time.time()
        result: dict[str, Any] = {
            "session_id": self.session_id,
            "repo_path": self.repo_path,
            "duration_seconds": round(now - self.created_at, 1),
            "tool_calls": self.tool_calls,
            "scope": self.scope_label(),
        }
        if self.score_at_start is not None and self.last_scan_score is not None:
            result["score_start"] = self.score_at_start
            result["score_end"] = self.last_scan_score
            result["score_delta"] = round(
                self.last_scan_score - self.score_at_start, 2
            )
        if self.selected_tasks:
            result["tasks_total"] = len(self.selected_tasks)
            result["tasks_completed"] = len(self.completed_task_ids)
            result["tasks_remaining"] = self.tasks_remaining()
        result["orchestration_metrics"] = self.metrics.to_dict()
        # Timing decomposition (WP-4)
        if self._total_tool_ms > 0 or self._total_inter_call_ms > 0:
            total_wall_ms = (now - self.created_at) * 1000
            result["timing"] = {
                "total_tool_ms": round(self._total_tool_ms, 1),
                "total_inter_call_ms": round(self._total_inter_call_ms, 1),
                "total_wall_ms": round(total_wall_ms, 1),
                "tool_pct": (
                    round(self._total_tool_ms / total_wall_ms * 100, 1)
                    if total_wall_ms > 0
                    else 0.0
                ),
            }
        return result

    # -- Task-queue leasing --------------------------------------------------

    def _reap_expired_leases(self, max_reclaim: int = 3) -> None:
        """Expire leases whose deadline has passed.

        Must be called while ``_lock`` is held.
        """
        now = time.time()
        expired_ids = [
            tid
            for tid, lease in self.active_leases.items()
            if lease["expires_at"] <= now
        ]
        for tid in expired_ids:
            lease = self.active_leases[tid]
            lease_duration = now - lease.get("acquired_at", now)
            self.metrics.total_lease_time_seconds += lease_duration
            self.metrics.tasks_expired += 1
            del self.active_leases[tid]
            self.task_reclaim_counts[tid] = self.task_reclaim_counts.get(tid, 0) + 1
            if self.task_reclaim_counts[tid] >= max_reclaim and tid not in self.failed_task_ids:
                self.failed_task_ids.append(tid)
                self.metrics.tasks_failed += 1

    def _effective_task_state(self, task_id: str) -> str:
        """Return the current state of a task ID.

        Must be called while ``_lock`` is held.
        Possible values: ``"pending"``, ``"claimed"``, ``"completed"``,
        ``"failed"``, ``"unknown"``.
        """
        if task_id in self.completed_task_ids:
            return "completed"
        if task_id in self.failed_task_ids:
            return "failed"
        lease = self.active_leases.get(task_id)
        if lease is not None:
            return "claimed" if lease["expires_at"] > time.time() else "pending"
        if self.selected_tasks:
            for t in self.selected_tasks:
                if t.get("id", t.get("task_id", "")) == task_id:
                    return "pending"
        return "unknown"

    def claim_task(
        self,
        agent_id: str,
        task_id: str | None = None,
        lease_ttl_seconds: int = 300,
        max_reclaim: int = 3,
    ) -> dict[str, Any] | None:
        """Claim the next pending task (FIFO) or a specific task by ID.

        Returns a dict with ``task`` and ``lease`` keys, or ``None``
        if no pending task is available.  Thread-safe via ``_lock``.
        """
        with self._lock:
            self._reap_expired_leases(max_reclaim)
            if not self.selected_tasks:
                return None

            # Phase G: explicit Claim-Guard — reject if already actively leased
            if task_id is not None:
                existing = self.active_leases.get(task_id)
                if existing and existing["expires_at"] > time.time():
                    self.metrics.duplicate_claims_attempted += 1
                    return None

            target_task: dict[str, Any] | None = None
            if task_id is not None:
                for t in self.selected_tasks:
                    tid = t.get("id", t.get("task_id", ""))
                    if tid == task_id:
                        if self._effective_task_state(task_id) == "pending":
                            target_task = t
                        break
            else:
                for t in self.selected_tasks:
                    tid = t.get("id", t.get("task_id", ""))
                    if self._effective_task_state(tid) == "pending":
                        target_task = t
                        break

            if target_task is None:
                return None

            tid = target_task.get("id", target_task.get("task_id", ""))
            now = time.time()
            self.active_leases[tid] = {
                "agent_id": agent_id,
                "acquired_at": now,
                "expires_at": now + lease_ttl_seconds,
                "lease_ttl_seconds": lease_ttl_seconds,
                "renew_count": 0,
            }
            self.metrics.tasks_claimed += 1
            if self.metrics.first_claim_at is None:
                self.metrics.first_claim_at = now
            self.touch()
            return {
                "task": target_task,
                "lease": {
                    "task_id": tid,
                    "agent_id": agent_id,
                    "acquired_at": now,
                    "expires_at": now + lease_ttl_seconds,
                    "lease_ttl_seconds": lease_ttl_seconds,
                },
            }

    def renew_lease(
        self,
        agent_id: str,
        task_id: str,
        extend_seconds: int = 300,
    ) -> dict[str, Any]:
        """Extend the deadline of an active lease.

        Returns a status dict.  Possible ``status`` values: ``"renewed"``,
        ``"not_found"``, ``"wrong_agent"``, ``"expired"``.
        Thread-safe via ``_lock``.
        """
        with self._lock:
            lease = self.active_leases.get(task_id)
            if lease is None:
                return {
                    "task_id": task_id,
                    "status": "not_found",
                    "error": "No active lease for this task.",
                }
            if lease["agent_id"] != agent_id:
                return {
                    "task_id": task_id,
                    "status": "wrong_agent",
                    "error": "Lease belongs to a different agent.",
                }
            if lease["expires_at"] <= time.time():
                return {
                    "task_id": task_id,
                    "status": "expired",
                    "error": "Lease has already expired.",
                }
            lease["expires_at"] += extend_seconds
            lease["renew_count"] += 1
            self.touch()
            return {
                "task_id": task_id,
                "agent_id": agent_id,
                "expires_at": lease["expires_at"],
                "renew_count": lease["renew_count"],
                "status": "renewed",
            }

    def release_task(
        self,
        agent_id: str,
        task_id: str,
        max_reclaim: int = 3,
    ) -> dict[str, Any]:
        """Release a claimed task back to the pending pool.

        Returns a status dict.  Possible ``status`` values: ``"released"``,
        ``"failed"``, ``"not_found"``, ``"wrong_agent"``.
        Thread-safe via ``_lock``.
        """
        with self._lock:
            lease = self.active_leases.get(task_id)
            if lease is None:
                return {
                    "task_id": task_id,
                    "status": "not_found",
                    "error": "No active lease for this task.",
                }
            if lease["agent_id"] != agent_id:
                return {
                    "task_id": task_id,
                    "status": "wrong_agent",
                    "error": "Lease belongs to a different agent.",
                }
            # Track lease duration before removing
            now = time.time()
            self.metrics.total_lease_time_seconds += now - lease.get("acquired_at", now)
            del self.active_leases[task_id]
            self.task_reclaim_counts[task_id] = (
                self.task_reclaim_counts.get(task_id, 0) + 1
            )
            reclaim_count = self.task_reclaim_counts[task_id]
            if reclaim_count >= max_reclaim:
                if task_id not in self.failed_task_ids:
                    self.failed_task_ids.append(task_id)
                    self.metrics.tasks_failed += 1
                state = "failed"
            else:
                state = "released"
            self.metrics.tasks_released += 1
            self.touch()
            return {
                "task_id": task_id,
                "status": state,
                "reclaim_count": reclaim_count,
            }

    def complete_task(
        self,
        agent_id: str,
        task_id: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Mark a claimed task as completed.

        Returns a status dict.  Possible ``status`` values: ``"completed"``,
        ``"already_completed"``, ``"not_found"``, ``"wrong_agent"``.
        Thread-safe via ``_lock``.
        """
        with self._lock:
            if task_id in self.completed_task_ids:
                return {"task_id": task_id, "status": "already_completed"}
            lease = self.active_leases.get(task_id)
            if lease is None:
                task_exists = self.selected_tasks and any(
                    t.get("id", t.get("task_id", "")) == task_id
                    for t in self.selected_tasks
                )
                if task_exists:
                    return {
                        "task_id": task_id,
                        "status": "not_found",
                        "error": "Task must be claimed before completing.",
                    }
                return {
                    "task_id": task_id,
                    "status": "not_found",
                    "error": "Task not found in this session.",
                }
            if lease["agent_id"] != agent_id:
                return {
                    "task_id": task_id,
                    "status": "wrong_agent",
                    "error": "Lease belongs to a different agent.",
                }
            # Track lease duration
            now = time.time()
            self.metrics.total_lease_time_seconds += now - lease.get("acquired_at", now)
            del self.active_leases[task_id]
            self.completed_task_ids.append(task_id)
            # Phase F: store completion result (bugfix — was previously discarded)
            if result is not None:
                self.completed_results[task_id] = result
            self.metrics.tasks_completed += 1
            if self.metrics.first_completion_at is None:
                self.metrics.first_completion_at = now
            self.metrics.last_completion_at = now
            self.touch()
            return {
                "task_id": task_id,
                "status": "completed",
                "result_stored": result is not None,
            }

    def queue_status(self) -> dict[str, Any]:
        """Return a snapshot of the task queue categorised by state.

        Triggers expired-lease reaping before computing the snapshot.
        Thread-safe via ``_lock``.
        """
        with self._lock:
            self._reap_expired_leases()
            if not self.selected_tasks:
                return {
                    "total": 0,
                    "pending_count": 0,
                    "claimed_count": 0,
                    "completed_count": 0,
                    "failed_count": 0,
                    "pending_tasks": [],
                    "claimed_tasks": [],
                    "completed_task_ids": [],
                    "failed_task_ids": [],
                }
            pending: list[dict[str, Any]] = []
            claimed: list[dict[str, Any]] = []
            for t in self.selected_tasks:
                tid = t.get("id", t.get("task_id", ""))
                state = self._effective_task_state(tid)
                if state == "pending":
                    pending.append(
                        {
                            "id": tid,
                            "signal": t.get("signal", ""),
                            "title": t.get("title", ""),
                        }
                    )
                elif state == "claimed":
                    lease = self.active_leases.get(tid, {})
                    claimed.append(
                        {
                            "id": tid,
                            "signal": t.get("signal", ""),
                            "agent_id": lease.get("agent_id"),
                            "expires_at": lease.get("expires_at"),
                        }
                    )
            return {
                "total": len(self.selected_tasks),
                "pending_count": len(pending),
                "claimed_count": len(claimed),
                "completed_count": len(self.completed_task_ids),
                "failed_count": len(self.failed_task_ids),
                "pending_tasks": pending,
                "claimed_tasks": claimed,
                "completed_task_ids": list(self.completed_task_ids),
                "failed_task_ids": list(self.failed_task_ids),
            }

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise session to a JSON-compatible dict."""
        return {
            "schema_version": _SCHEMA_VERSION,
            "session_id": self.session_id,
            "repo_path": self.repo_path,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "ttl_seconds": self.ttl_seconds,
            "signals": self.signals,
            "exclude_signals": self.exclude_signals,
            "target_path": self.target_path,
            "exclude_paths": self.exclude_paths,
            "last_scan_score": self.last_scan_score,
            "last_scan_top_signals": self.last_scan_top_signals,
            "last_scan_finding_count": self.last_scan_finding_count,
            "baseline_file": self.baseline_file,
            "score_at_start": self.score_at_start,
            "selected_tasks": self.selected_tasks,
            "completed_task_ids": self.completed_task_ids,
            "active_leases": self.active_leases,
            "failed_task_ids": self.failed_task_ids,
            "task_reclaim_counts": self.task_reclaim_counts,
            "completed_results": self.completed_results,
            "guardrails": self.guardrails,
            "guardrails_prompt_block": self.guardrails_prompt_block,
            "tool_calls": self.tool_calls,
            "metrics": self.metrics.to_dict(),
            "phase": self.phase,
            "trace": self.trace,
            "run_history": self.run_history,
            "effectiveness_thresholds": self.effectiveness_thresholds,
            "diagnostic_hypotheses": self.diagnostic_hypotheses,
            "git_head_at_plan": self.git_head_at_plan,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DriftSession:
        """Deserialise a session from a dict (e.g. loaded from disk)."""
        metrics_data = data.get("metrics")
        metrics = (
            OrchestrationMetrics.from_dict(metrics_data)
            if isinstance(metrics_data, dict)
            else OrchestrationMetrics()
        )
        return cls(
            session_id=data["session_id"],
            repo_path=data["repo_path"],
            created_at=data.get("created_at", time.time()),
            last_activity=data.get("last_activity", time.time()),
            ttl_seconds=data.get("ttl_seconds", _DEFAULT_TTL_SECONDS),
            signals=data.get("signals"),
            exclude_signals=data.get("exclude_signals"),
            target_path=data.get("target_path"),
            exclude_paths=data.get("exclude_paths"),
            last_scan_score=data.get("last_scan_score"),
            last_scan_top_signals=data.get("last_scan_top_signals"),
            last_scan_finding_count=data.get("last_scan_finding_count"),
            baseline_file=data.get("baseline_file"),
            score_at_start=data.get("score_at_start"),
            selected_tasks=data.get("selected_tasks"),
            completed_task_ids=data.get("completed_task_ids", []),
            active_leases=data.get("active_leases", {}),
            failed_task_ids=data.get("failed_task_ids", []),
            task_reclaim_counts=data.get("task_reclaim_counts", {}),
            completed_results=data.get("completed_results", {}),
            guardrails=data.get("guardrails"),
            guardrails_prompt_block=data.get("guardrails_prompt_block"),
            tool_calls=data.get("tool_calls", 0),
            metrics=metrics,
            phase=data.get("phase", "init"),
            trace=data.get("trace", []),
            run_history=data.get("run_history", []),
            effectiveness_thresholds=data.get(
                "effectiveness_thresholds", dict(_DEFAULT_EFFECTIVENESS_THRESHOLDS)
            ),
            diagnostic_hypotheses=data.get("diagnostic_hypotheses", {}),
            git_head_at_plan=data.get("git_head_at_plan"),
        )


class SessionManager:
    """Singleton manager for active MCP sessions.

    Mirrors the ``BaselineManager`` pattern from ``incremental.py``:
    one global instance, keyed by ``session_id`` instead of repo path.
    Expired sessions are pruned lazily on access.
    """

    _instance: ClassVar[SessionManager | None] = None

    def __init__(self) -> None:
        self._sessions: dict[str, DriftSession] = {}

    # -- singleton -----------------------------------------------------------

    @classmethod
    def instance(cls) -> SessionManager:
        """Return the global singleton, creating it on first access."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None

    # -- CRUD ----------------------------------------------------------------

    def create(
        self,
        repo_path: str,
        *,
        signals: list[str] | None = None,
        exclude_signals: list[str] | None = None,
        target_path: str | None = None,
        exclude_paths: list[str] | None = None,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> str:
        """Create a new session and return its ``session_id``."""
        self.prune_expired()
        session_id = uuid.uuid4().hex
        session = DriftSession(
            session_id=session_id,
            repo_path=str(Path(repo_path).resolve()),
            ttl_seconds=ttl_seconds,
            signals=signals,
            exclude_signals=exclude_signals,
            target_path=target_path,
            exclude_paths=exclude_paths,
        )
        self._sessions[session_id] = session
        logger.debug("Session created: %s for %s", session_id[:8], repo_path)
        return session_id

    def get(self, session_id: str) -> DriftSession | None:
        """Return the session if it exists and is valid, else ``None``."""
        self.prune_expired()
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if not session.is_valid():
            del self._sessions[session_id]
            logger.debug("Session expired on access: %s", session_id[:8])
            return None
        return session

    def update(self, session_id: str, **kwargs: Any) -> DriftSession | None:
        """Update session fields. Returns updated session or ``None``."""
        session = self.get(session_id)
        if session is None:
            return None

        allowed_fields = {
            "signals",
            "exclude_signals",
            "target_path",
            "exclude_paths",
            "last_scan_score",
            "last_scan_top_signals",
            "last_scan_finding_count",
            "baseline_file",
            "score_at_start",
            "selected_tasks",
            "completed_task_ids",
            "guardrails",
            "guardrails_prompt_block",
        }

        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(session, key, value)
            else:
                logger.warning("Session update: ignoring unknown field %r", key)

        session.touch()
        return session

    def destroy(self, session_id: str) -> dict[str, Any] | None:
        """Remove a session and return its end summary, or ``None``."""
        session = self._sessions.pop(session_id, None)
        if session is None:
            return None
        summary = session.end_summary()
        logger.debug("Session destroyed: %s", session_id[:8])
        return summary

    def list_active(self) -> list[dict[str, Any]]:
        """Return compact summaries of all non-expired sessions."""
        self.prune_expired()
        return [s.summary() for s in self._sessions.values()]

    def prune_expired(self) -> int:
        """Remove all expired sessions. Returns count of pruned sessions."""
        expired = [
            sid for sid, s in self._sessions.items() if not s.is_valid()
        ]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.debug("Pruned %d expired session(s)", len(expired))
        return len(expired)

    # -- disk persistence ----------------------------------------------------

    def save_to_disk(
        self, session_id: str, directory: str | Path | None = None
    ) -> Path | None:
        """Persist a session to a JSON file. Returns the file path or ``None``.

        The file is written to ``directory`` (default: repo working directory)
        as ``.drift-session-{id_prefix}.json``.
        """
        session = self.get(session_id)
        if session is None:
            return None

        target_dir = Path(directory) if directory else Path(session.repo_path)
        filename = f".drift-session-{session_id[:8]}.json"
        filepath = target_dir / filename

        data = session.to_dict()
        filepath.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        logger.debug("Session saved to disk: %s", filepath)
        return filepath

    def load_from_disk(self, filepath: str | Path) -> str | None:
        """Load a session from a JSON file and register it.

        Returns the ``session_id`` or ``None`` if loading fails.
        """
        path = Path(filepath)
        if not path.is_file():
            logger.warning("Session file not found: %s", path)
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load session file %s: %s", path, exc)
            return None

        if not isinstance(data, dict) or "session_id" not in data:
            logger.warning("Invalid session file format: %s", path)
            return None

        session = DriftSession.from_dict(data)
        # Refresh activity timestamp so loaded session doesn't expire immediately
        session.last_activity = time.time()
        self._sessions[session.session_id] = session
        logger.debug(
            "Session loaded from disk: %s (%s)",
            session.session_id[:8],
            path,
        )
        return session.session_id

"""Patch engine API — transactional protocol for agent-driven code changes.

Three-phase protocol:
1. ``patch_begin``  — declare intent before editing.
2. ``patch_check``  — validate scope compliance after editing.
3. ``patch_commit`` — generate evidence record for the change.

Decision: ADR-074
"""

from __future__ import annotations

import logging as _logging
import subprocess
import time as _time
from pathlib import Path
from typing import Any

from drift.api._config import _emit_api_telemetry
from drift.api_helpers import _base_response
from drift.models._patch import (
    BlastRadius,
    DiffMetrics,
    PatchIntent,
    PatchStatus,
    PatchVerdict,
)

_log = _logging.getLogger("drift")


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_changed_files(repo_path: Path) -> list[str]:
    """Return posix-relative paths of files changed in the working tree."""
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", "--relative", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=repo_path,
            check=True,
            stdin=subprocess.DEVNULL,
        )
        return [line for line in proc.stdout.strip().splitlines() if line]
    except Exception:
        _log.warning("Could not detect changed files via git in %s", repo_path)
        return []


def _compute_diff_metrics(repo_path: Path) -> dict[str, Any]:
    """Compute line-level diff metrics from git diff --stat."""
    try:
        proc = subprocess.run(
            ["git", "diff", "--numstat", "--relative", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=repo_path,
            check=True,
            stdin=subprocess.DEVNULL,
        )
        lines_added = 0
        lines_removed = 0
        files_changed = 0
        for line in proc.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                files_changed += 1
                try:
                    lines_added += int(parts[0])
                    lines_removed += int(parts[1])
                except ValueError:
                    pass  # binary file: shows "-"
        return {
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "files_changed": files_changed,
        }
    except Exception:
        _log.warning("Could not compute diff metrics in %s", repo_path)
        return {"lines_added": 0, "lines_removed": 0, "files_changed": 0}


# ---------------------------------------------------------------------------
# patch_begin
# ---------------------------------------------------------------------------


def patch_begin(
    task_id: str,
    declared_files: list[str],
    expected_outcome: str,
    *,
    session_id: str | None = None,
    blast_radius: str = "local",
    forbidden_paths: list[str] | None = None,
    max_diff_lines: int | None = None,
    quality_constraints: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    constraints: list[str] | None = None,
) -> dict[str, Any]:
    """Declare intent before editing.

    Returns a dict with the serialised ``PatchIntent`` and agent guidance.
    """
    start_ms = _time.monotonic()

    intent = PatchIntent(
        task_id=task_id,
        session_id=session_id,
        declared_files=declared_files,
        expected_outcome=expected_outcome,
        blast_radius=BlastRadius(blast_radius),
        forbidden_paths=forbidden_paths or [],
        max_diff_lines=max_diff_lines,
        quality_constraints=quality_constraints or [],
        acceptance_criteria=acceptance_criteria or [],
        constraints=constraints or [],
    )

    result = _base_response(
        task_id=task_id,
        intent=intent.to_api_dict(),
        agent_instruction=(
            f"PatchIntent registered for {task_id}. "
            f"You may now edit: {', '.join(declared_files)}. "
            f"Call drift_patch_check when done."
        ),
        next_tool_call={
            "tool": "drift_patch_check",
            "params": {
                "task_id": task_id,
                "declared_files": declared_files,
            },
        },
    )

    elapsed = int((_time.monotonic() - start_ms) * 1000)
    _emit_api_telemetry(
        tool_name="patch_begin",
        params={"task_id": task_id},
        status="ok",
        elapsed_ms=elapsed,
        result=result,
        error=None,
        repo_root=None,
    )
    return result


# ---------------------------------------------------------------------------
# patch_check
# ---------------------------------------------------------------------------


def patch_check(
    task_id: str,
    declared_files: list[str],
    path: str | Path = ".",
    *,
    forbidden_paths: list[str] | None = None,
    max_diff_lines: int | None = None,
) -> dict[str, Any]:
    """Validate scope compliance after editing.

    Returns a dict with the ``PatchVerdict`` and merge readiness.
    """
    start_ms = _time.monotonic()
    repo_path = Path(path).resolve()
    forbidden = set(forbidden_paths or [])

    # Gather changed files
    changed_files = _get_changed_files(repo_path)
    declared_set = set(declared_files)

    # Scope violations: files changed but not declared
    scope_violations = [f for f in changed_files if f not in declared_set]
    scope_compliance = len(scope_violations) == 0

    # Forbidden path violations
    forbidden_violations = [f for f in changed_files if f in forbidden]

    # Diff metrics
    diff_metrics = _compute_diff_metrics(repo_path)

    # Determine status and reasons
    reasons: list[str] = []
    status = PatchStatus.CLEAN

    if scope_violations:
        status = PatchStatus.REVIEW_REQUIRED
        reasons.append(
            f"Scope violation: {len(scope_violations)} file(s) outside declared scope:"
            f" {scope_violations}"
        )

    if forbidden_violations:
        status = PatchStatus.REVIEW_REQUIRED
        reasons.append(f"Forbidden path touched: {forbidden_violations}")

    if max_diff_lines is not None:
        total_lines = diff_metrics.get("lines_added", 0) + diff_metrics.get("lines_removed", 0)
        if total_lines > max_diff_lines:
            status = PatchStatus.REVIEW_REQUIRED
            reasons.append(
                f"Diff size ({total_lines} lines) exceeds max_diff_lines ({max_diff_lines})"
            )

    if not reasons:
        reasons.append("All checks passed")

    merge_readiness = "ready" if status == PatchStatus.CLEAN else "manual_review"

    verdict = PatchVerdict(
        task_id=task_id,
        status=status,
        scope_compliance=scope_compliance,
        scope_violations=scope_violations,
        diff_metrics=DiffMetrics(
            lines_added=diff_metrics.get("lines_added", 0),
            lines_removed=diff_metrics.get("lines_removed", 0),
            files_changed=diff_metrics.get("files_changed", 0),
        ),
        architecture_impact=[],
        test_passed=None,
        acceptance_met=[],
        reasons=reasons,
        evidence={},
        merge_readiness=merge_readiness,
    )

    agent_instruction = (
        f"Patch check {status.value}: {'; '.join(reasons)}. "
        + (
            "Safe to commit."
            if status == PatchStatus.CLEAN
            else "Manual review recommended before commit."
        )
    )

    result = _base_response(
        task_id=task_id,
        status=status.value,
        scope_compliance=scope_compliance,
        scope_violations=scope_violations,
        diff_metrics=diff_metrics,
        merge_readiness=merge_readiness,
        reasons=reasons,
        verdict=verdict.to_api_dict(),
        agent_instruction=agent_instruction,
        next_tool_call={
            "tool": "drift_patch_commit" if status == PatchStatus.CLEAN else "drift_fix_plan",
            "params": {"task_id": task_id},
        },
    )

    elapsed = int((_time.monotonic() - start_ms) * 1000)
    _emit_api_telemetry(
        tool_name="patch_check",
        params={"task_id": task_id},
        status="ok",
        elapsed_ms=elapsed,
        result=result,
        error=None,
        repo_root=repo_path,
    )
    return result


# ---------------------------------------------------------------------------
# patch_commit
# ---------------------------------------------------------------------------


def patch_commit(
    task_id: str,
    declared_files: list[str],
    expected_outcome: str,
    path: str | Path = ".",
    *,
    session_id: str | None = None,
    verdict_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate evidence record for a completed patch.

    If ``verdict_override`` is provided, it is used directly; otherwise
    ``patch_check`` is called internally to produce the verdict.
    """
    start_ms = _time.monotonic()
    repo_path = Path(path).resolve()

    # Build intent
    intent = PatchIntent(
        task_id=task_id,
        session_id=session_id,
        declared_files=declared_files,
        expected_outcome=expected_outcome,
    )

    # Get or compute verdict
    if verdict_override is not None:
        verdict_dict = verdict_override
        merge_readiness = verdict_override.get("merge_readiness", "manual_review")
    else:
        check_result = patch_check(
            task_id=task_id,
            declared_files=declared_files,
            path=repo_path,
        )
        verdict_dict = check_result.get("verdict", {})
        merge_readiness = check_result.get("merge_readiness", "manual_review")

    evidence = {
        "task_id": task_id,
        "intent": intent.to_api_dict(),
        "verdict": verdict_dict,
    }

    result = _base_response(
        task_id=task_id,
        evidence=evidence,
        merge_readiness=merge_readiness,
        agent_instruction=(
            f"Evidence record generated for {task_id}. "
            f"Merge readiness: {merge_readiness}."
        ),
    )

    elapsed = int((_time.monotonic() - start_ms) * 1000)
    _emit_api_telemetry(
        tool_name="patch_commit",
        params={"task_id": task_id},
        status="ok",
        elapsed_ms=elapsed,
        result=result,
        error=None,
        repo_root=repo_path,
    )
    return result

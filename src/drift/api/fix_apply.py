"""fix_apply — apply high-confidence patches to the local working tree (ADR-076).

Entry point for ``drift fix-plan --apply``.  Always requires a clean git state.
Python-only scope in v1; libcst must be installed (``drift[autopatch]``).
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from drift.api import fix_plan as api_fix_plan
from drift.api._config import _emit_api_telemetry
from drift.api_helpers import _base_response, _error_response

logger = logging.getLogger("drift")

# Minimum automation bar: only HIGH-confidence, LOCAL-scope, LOW-risk tasks
_MIN_AUTOMATION_FIT = "high"
_MIN_CHANGE_SCOPE = "local"
_MAX_REVIEW_RISK = "low"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _is_git_clean(repo_path: Path) -> bool:
    """Return True when the working tree has no uncommitted changes."""
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=repo_path,
            check=True,
            stdin=subprocess.DEVNULL,
        )
        return proc.stdout.strip() == ""
    except Exception:
        logger.debug("Could not determine git status in %s", repo_path)
        return False


# ---------------------------------------------------------------------------
# Task filter
# ---------------------------------------------------------------------------


def _is_auto_applicable(task: Any) -> bool:
    """Return True when *task* meets the minimum auto-apply bar."""
    fit = getattr(task, "automation_fit", None)
    scope = getattr(task, "change_scope", None)
    risk = getattr(task, "review_risk", None)

    # Compare against string values (StrEnum is str-compatible)
    if str(fit).lower() != _MIN_AUTOMATION_FIT:
        return False
    if str(scope).lower() != _MIN_CHANGE_SCOPE:
        return False
    return str(risk).lower() == _MAX_REVIEW_RISK


# ---------------------------------------------------------------------------
# Finding reconstruction from AgentTask
# ---------------------------------------------------------------------------


def _task_to_finding(task: Any) -> Any | None:
    """Build a minimal Finding from an AgentTask for patch generation.

    Returns None if the task lacks the required fields.
    """
    try:
        from drift.models import Finding

        file_path = task.file_path
        if not file_path:
            return None

        metadata: dict[str, Any] = dict(task.metadata or {})
        edit_kind = metadata.get("fix_template_class") or metadata.get("edit_kind") or ""

        # Infer language from file extension if not in metadata
        language: str | None = metadata.get("language")
        if language is None:
            suffix = Path(file_path).suffix.lower()
            _lang_map = {".py": "python", ".ts": "typescript", ".js": "javascript"}
            language = _lang_map.get(suffix)

        metadata["edit_kind"] = edit_kind

        return Finding(
            signal_type=task.signal_type,
            severity=task.severity,
            score=0.5,
            title=task.title,
            description=task.description,
            file_path=Path(file_path),
            start_line=task.start_line,
            end_line=task.end_line,
            symbol=task.symbol,
            language=language,
            metadata=metadata,
        )
    except Exception as exc:
        logger.debug("_task_to_finding: failed for task %s: %s", getattr(task, "id", "?"), exc)
        return None


# ---------------------------------------------------------------------------
# Core apply loop
# ---------------------------------------------------------------------------


def _apply_patches(
    repo_path: Path,
    tasks: list[Any],
    dry_run: bool,
) -> list[dict[str, Any]]:
    """Run the patch-generate (and optionally write) loop for *tasks*.

    Returns a list of patch result dicts.
    """
    from drift.patch_writer import get_writer

    results: list[dict[str, Any]] = []

    for task in tasks:
        edit_kind: str = (task.metadata or {}).get("fix_template_class", "") or (
            task.metadata or {}
        ).get("edit_kind", "")

        if not edit_kind:
            results.append(
                {
                    "task_id": task.id,
                    "status": "skipped",
                    "reason": "no edit_kind in task metadata",
                }
            )
            continue

        writer = get_writer(edit_kind)
        if writer is None:
            results.append(
                {
                    "task_id": task.id,
                    "edit_kind": edit_kind,
                    "status": "unsupported",
                    "reason": f"No PatchWriter registered for edit_kind={edit_kind!r}",
                }
            )
            continue

        finding = _task_to_finding(task)
        if finding is None:
            results.append(
                {
                    "task_id": task.id,
                    "edit_kind": edit_kind,
                    "status": "failed",
                    "reason": "Could not reconstruct Finding from task (missing file_path/symbol?)",
                }
            )
            continue

        if not writer.can_write(finding):
            results.append(
                {
                    "task_id": task.id,
                    "edit_kind": edit_kind,
                    "file": str(finding.file_path),
                    "status": "unsupported",
                    "reason": "PatchWriter.can_write returned False",
                }
            )
            continue

        file_path = repo_path / str(finding.file_path)
        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception as exc:
            results.append(
                {
                    "task_id": task.id,
                    "edit_kind": edit_kind,
                    "file": str(finding.file_path),
                    "status": "failed",
                    "reason": f"Could not read file: {exc}",
                }
            )
            continue

        patch_result = writer.generate_patch(finding, source)

        entry: dict[str, Any] = {
            "task_id": task.id,
            "edit_kind": edit_kind,
            "file": str(finding.file_path),
            "status": str(patch_result.status),
            "reason": patch_result.reason,
            "diff": patch_result.diff,
        }

        if patch_result.status.value in ("generated",) and not dry_run:
            # Write the patched source to disk
            try:
                assert patch_result.patched_source is not None  # noqa: S101
                file_path.write_text(patch_result.patched_source, encoding="utf-8")
                entry["status"] = "applied"
                entry["written"] = True
            except Exception as exc:
                entry["status"] = "failed"
                entry["reason"] = f"Write error: {exc}"
                entry["written"] = False

        results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fix_apply(
    path: str | Path,
    *,
    signal: str | None = None,
    max_tasks: int = 10,
    dry_run: bool = True,
    yes: bool = False,
    target_path: str | None = None,
    exclude_paths: list[str] | None = None,
    require_clean_git: bool = True,
) -> dict[str, Any]:
    """Generate and (optionally) apply high-confidence auto-patches.

    Parameters
    ----------
    path:
        Repository root.
    signal:
        Restrict to a single signal (e.g. ``"EDS"``).
    max_tasks:
        Maximum number of tasks to consider from the fix plan.
    dry_run:
        When *True* (default), generate patches but do not write files.
    yes:
        When *True*, skip the clean-git-state requirement (for testing only).
        Not exposed as a CLI flag in unsafe form — CLI handles confirmation UX.
    target_path:
        Restrict to findings inside this subpath.
    exclude_paths:
        Exclude findings inside these subpaths.
    require_clean_git:
        When *True* (default), abort if the working tree is dirty.

    Returns
    -------
    dict
        API-standard response with ``patches``, ``summary``, and metadata fields.
    """
    repo_path = Path(path).resolve()
    _emit_api_telemetry(
        tool_name="fix_apply",
        params={"path": str(repo_path), "dry_run": dry_run, "signal": signal},
        status="start",
        elapsed_ms=0,
        result=None,
        error=None,
        repo_root=repo_path,
    )

    base = _base_response()

    # --- Git state gate -------------------------------------------------------
    if require_clean_git and not _is_git_clean(repo_path):
        return {
            **base,
            **_error_response(
                "dirty_git_state",
                (
                    "Working tree has uncommitted changes. "
                    "Please commit or stash your changes before applying patches. "
                    "Use --dry-run to preview patches without modifying files."
                ),
            ),
            "dry_run": dry_run,
            "patches": [],
            "summary": {"total": 0, "applied": 0, "skipped": 0, "failed": 0, "unsupported": 0},
        }

    # --- Load fix plan --------------------------------------------------------
    try:
        plan = api_fix_plan(
            repo_path,
            signal=signal,
            max_tasks=max_tasks,
            automation_fit_min=_MIN_AUTOMATION_FIT,
            target_path=target_path,
            exclude_paths=exclude_paths,
        )
    except Exception as exc:
        logger.warning("fix_apply: fix_plan failed: %s", exc)
        return {
            **base,
            **_error_response("fix_plan_failed", str(exc)),
            "dry_run": dry_run,
            "patches": [],
            "summary": {"total": 0, "applied": 0, "skipped": 0, "failed": 0, "unsupported": 0},
        }

    if plan.get("error"):
        return {
            **base,
            **_error_response(plan.get("error", "fix_plan_error"), plan.get("message", "")),
            "dry_run": dry_run,
            "patches": [],
            "summary": {"total": 0, "applied": 0, "skipped": 0, "failed": 0, "unsupported": 0},
        }

    tasks = plan.get("tasks", [])

    # --- Filter to auto-applicable tasks -------------------------------------
    applicable = [t for t in tasks if _is_auto_applicable(t)]

    if not applicable:
        return {
            **base,
            "dry_run": dry_run,
            "patches": [],
            "summary": {"total": 0, "applied": 0, "skipped": 0, "failed": 0, "unsupported": 0},
            "agent_instruction": (
                "No tasks met the auto-apply bar (HIGH automation_fit + LOCAL scope + LOW risk). "
                "Review the full fix-plan output to identify tasks requiring manual intervention."
            ),
        }

    # --- Generate / apply patches --------------------------------------------
    patch_entries = _apply_patches(repo_path, applicable, dry_run=dry_run)

    # --- Summary --------------------------------------------------------------
    summary: dict[str, int] = {
        "total": len(patch_entries),
        "applied": sum(1 for p in patch_entries if p["status"] == "applied"),
        "generated": sum(1 for p in patch_entries if p["status"] == "generated"),
        "skipped": sum(1 for p in patch_entries if p["status"] == "skipped"),
        "failed": sum(1 for p in patch_entries if p["status"] == "failed"),
        "unsupported": sum(1 for p in patch_entries if p["status"] == "unsupported"),
    }

    agent_instruction = (
        f"Previewed {summary['total']} patch(es). "
        "Run `drift fix-plan --apply` (without --dry-run) to write changes to disk."
        if dry_run
        else (
            f"Applied {summary['applied']}/{summary['total']} patch(es). "
            "Verify with `drift analyze --repo .` and run your test suite."
        )
    )

    return {
        **base,
        "dry_run": dry_run,
        "patches": patch_entries,
        "summary": summary,
        "agent_instruction": agent_instruction,
    }

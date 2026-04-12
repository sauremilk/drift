"""Shadow-Verify endpoint — scope-bounded full re-scan for cross-file-risky edits.

For fix_intent edit_kinds classified as cross-file-risky (e.g. remove_import,
decouple_modules, extract_module, rename_symbol), drift_nudge uses incremental
estimation for cross-file signals and is therefore insufficient to confirm that
a repair had no unintended side effects.

shadow_verify() runs a full non-incremental analysis on the repository and then
filters findings to the supplied ``scope_files`` — the union of the task's
allowed_files, related_files and the related_files of directly adjacent tasks in
the task graph.  The result is compared against the current baseline to surface
any new findings introduced in scope.

ADR-064 introduced this endpoint.
"""

from __future__ import annotations

import time as _time
from pathlib import Path
from typing import Any

from drift.api._config import (
    _emit_api_telemetry,
    _load_config_cached,
    _log,
    _warn_config_issues,
)
from drift.api_helpers import (
    DONE_SAFE_TO_COMMIT,
    _base_response,
    _error_response,
    _finding_concise,
    _next_step_contract,
    shape_for_profile,
    signal_abbrev,
)
from drift.analyzer import analyze_repo
from drift.incremental import BaselineManager


def _shadow_verify_agent_instruction(*, shadow_clean: bool, new_count: int) -> str:
    if shadow_clean:
        return (
            "shadow_verify PASSED — no new findings in scope. "
            "The fix is safe from a cross-file perspective. "
            "Proceed to drift_nudge for a final score sanity-check, then commit."
        )
    return (
        f"shadow_verify FAILED — {new_count} new finding(s) detected in scope. "
        "The repair introduced regressions in related files. "
        "Revert the last edit and re-analyse with drift_fix_plan before retrying."
    )


def shadow_verify(
    path: str | Path = ".",
    *,
    scope_files: list[str] | None = None,
    uncommitted: bool = True,
    response_profile: str | None = None,
) -> dict[str, Any]:
    """Run a scope-bounded full re-scan and compare against the baseline.

    Unlike drift_nudge, this function runs a *full* non-incremental analysis
    so that cross-file signals (co_change_coupling, circular_import,
    fan_out_explosion, architecture_violation, …) are computed with exact
    confidence rather than incremental estimation.

    Parameters
    ----------
    path:
        Repository root directory.
    scope_files:
        List of posix-relative file paths to include in the comparison.
        Findings outside this scope are ignored.  When ``None`` or empty,
        all findings are compared (full-repo shadow verify).
    uncommitted:
        Passed through for baseline freshness context only; the analysis
        itself always covers the current working-tree state.
    response_profile:
        Optional profile to compact the response payload.

    Returns
    -------
    dict
        ``shadow_clean``     — True when no new findings exist within scope.
        ``new_findings_in_scope``  — list of findings introduced by the edit.
        ``resolved_findings_in_scope`` — list of findings resolved by the edit.
        ``delta``            — score change (positive = regression).
        ``scope_files``      — the file scope that was checked.
        ``safe_to_merge``    — True when shadow_clean and delta <= 0.
        ``agent_instruction`` — natural-language guidance for the agent.
        ``next_tool`` / ``done_when`` — ADR-024 next-step contract.
    """
    start_ms = _time.monotonic()
    repo_path = Path(path).resolve()

    params: dict[str, Any] = {
        "path": str(path),
        "scope_files": scope_files or [],
        "uncommitted": uncommitted,
    }

    def elapsed_ms() -> int:
        return int((_time.monotonic() - start_ms) * 1_000)

    try:
        cfg = _load_config_cached(repo_path)
        _warn_config_issues(cfg)

        # ------------------------------------------------------------------ #
        # Full non-incremental analysis                                        #
        # ------------------------------------------------------------------ #
        analysis = analyze_repo(repo_path, config=cfg)

        # ------------------------------------------------------------------ #
        # Baseline comparison                                                  #
        # ------------------------------------------------------------------ #
        mgr = BaselineManager.instance()
        stored = mgr.get(repo_path, config=cfg)

        # Build a scope set for filtering — empty set means "all files".
        scope_set: set[str] = set(scope_files) if scope_files else set()

        def _in_scope(finding: Any) -> bool:
            if not scope_set:
                return True
            fp = finding.file_path.as_posix() if finding.file_path else ""
            return fp in scope_set

        current_findings = [f for f in analysis.findings if _in_scope(f)]

        if stored is not None:
            baseline_findings = [f for f in stored.snapshot.findings if _in_scope(f)]
        else:
            # No baseline → treat every current finding as new.
            baseline_findings = []

        # Rough finding identity: signal_type + file + title
        def _finding_key(f: Any) -> str:
            fp = f.file_path.as_posix() if getattr(f, "file_path", None) else ""
            return f"{f.signal_type}:{fp}:{f.title}"

        baseline_keys: set[str] = {_finding_key(f) for f in baseline_findings}
        current_keys: set[str] = {_finding_key(f) for f in current_findings}

        new_findings = [f for f in current_findings if _finding_key(f) not in baseline_keys]
        resolved_findings = [f for f in baseline_findings if _finding_key(f) not in current_keys]

        # Score delta (positive = regression)
        baseline_score = stored.snapshot.drift_score if stored is not None else 0.0
        current_score = analysis.drift_score
        delta = round(current_score - baseline_score, 4)

        shadow_clean = len(new_findings) == 0
        safe_to_merge = shadow_clean and delta <= 0.0

        # ------------------------------------------------------------------ #
        # Serialize findings                                                   #
        # ------------------------------------------------------------------ #
        new_serialized = [_finding_concise(f) for f in new_findings[:20]]
        resolved_serialized = [_finding_concise(f) for f in resolved_findings[:20]]

        agent_instruction = _shadow_verify_agent_instruction(
            shadow_clean=shadow_clean,
            new_count=len(new_findings),
        )

        if safe_to_merge:
            next_contract = _next_step_contract(
                next_tool="drift_nudge",
                done_when=DONE_SAFE_TO_COMMIT,
            )
        else:
            next_contract = _next_step_contract(
                next_tool="drift_fix_plan",
                done_when=DONE_SAFE_TO_COMMIT,
                fallback_tool="drift_scan",
                fallback_params={"response_detail": "concise"},
            )

        resp = _base_response(
            params=params,
            elapsed_ms=elapsed_ms(),
        ) | {
            "shadow_clean": shadow_clean,
            "safe_to_merge": safe_to_merge,
            "delta": delta,
            "scope_files": sorted(scope_set) if scope_set else [],
            "scope_file_count": len(scope_set),
            "new_finding_count": len(new_findings),
            "resolved_finding_count": len(resolved_findings),
            "new_findings_in_scope": new_serialized,
            "resolved_findings_in_scope": resolved_serialized,
            "agent_instruction": agent_instruction,
        } | next_contract

        _emit_api_telemetry("shadow_verify", params=params, elapsed_ms=elapsed_ms())
        return shape_for_profile(resp, response_profile)

    except Exception as exc:  # noqa: BLE001
        _log.exception("shadow_verify failed: %s", exc)
        return _error_response(
            "shadow_verify_failed",
            f"shadow_verify encountered an unexpected error: {exc}",
            recoverable=True,
            recovery_tool_call={"tool": "drift_scan", "params": {"path": str(path)}},
        )

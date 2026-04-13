"""Verify endpoint — binary pass/fail coherence verification for post-edit workflows.

Provides a single, CI-integrable verdict for the question:
"Did this edit degrade structural coherence?"

Wraps ``shadow_verify()`` with a Pass/Fail envelope suitable for CLI exit
codes, MCP tool responses, and CI pipeline gating.

Decision: ADR-070
"""

from __future__ import annotations

import time as _time
from pathlib import Path
from typing import Any

from drift.api._config import (
    _emit_api_telemetry,
    _log,
)
from drift.api.diff import diff as diff_api
from drift.api.shadow_verify import shadow_verify
from drift.api_helpers import (
    _base_response,
    _next_step_contract,
    shape_for_profile,
)
from drift.next_step_contract import (
    DONE_SAFE_TO_COMMIT,
    _error_response,
)


def _verify_agent_instruction(*, passed: bool, blocking_reasons: list[dict[str, Any]]) -> str:
    if passed:
        return (
            "verify PASSED — no structural coherence degradation detected. "
            "The edit is safe to commit."
        )
    reason_summary = "; ".join(r.get("reason", "") for r in blocking_reasons[:3])
    return (
        f"verify FAILED — {len(blocking_reasons)} blocking reason(s): {reason_summary}. "
        "Use drift_fix_plan to get a prioritized repair plan."
    )


def _direction_from_delta(delta: float) -> str:
    if delta < -0.001:
        return "improving"
    if delta > 0.001:
        return "degrading"
    return "stable"


def _validate_verify_modes(
    *,
    ref: str | None,
    uncommitted: bool,
    staged_only: bool,
    baseline: str | None,
) -> dict[str, Any] | None:
    if uncommitted and staged_only:
        return _error_response(
            "DRIFT-1012",
            "Options 'uncommitted' and 'staged_only' are mutually exclusive.",
            invalid_fields=[
                {
                    "field": "uncommitted",
                    "value": uncommitted,
                    "reason": "Cannot be true when staged_only=true",
                },
                {
                    "field": "staged_only",
                    "value": staged_only,
                    "reason": "Cannot be true when uncommitted=true",
                },
            ],
        )

    if ref and uncommitted:
        return _error_response(
            "DRIFT-1012",
            "Option 'ref' requires uncommitted=false.",
            invalid_fields=[
                {
                    "field": "ref",
                    "value": ref,
                    "reason": "Explicit git refs are incompatible with uncommitted=true",
                },
                {
                    "field": "uncommitted",
                    "value": uncommitted,
                    "reason": "Set to false when ref is provided",
                },
            ],
            suggested_fix={
                "action": "Use ref mode with uncommitted disabled",
                "example_call": {
                    "tool": "drift_verify",
                    "params": {"ref": ref, "uncommitted": False},
                },
            },
        )

    if ref and staged_only:
        return _error_response(
            "DRIFT-1012",
            "Options 'ref' and 'staged_only' are mutually exclusive.",
            invalid_fields=[
                {
                    "field": "ref",
                    "value": ref,
                    "reason": "Staged-only verification always compares against HEAD index",
                },
                {
                    "field": "staged_only",
                    "value": staged_only,
                    "reason": "Cannot be combined with explicit git ref comparison",
                },
            ],
        )

    if ref and baseline:
        return _error_response(
            "DRIFT-1012",
            "Options 'ref' and 'baseline' are mutually exclusive.",
            invalid_fields=[
                {
                    "field": "ref",
                    "value": ref,
                    "reason": "Choose either git-ref comparison or baseline-file comparison",
                },
                {
                    "field": "baseline",
                    "value": baseline,
                    "reason": "Choose either baseline-file comparison or git-ref comparison",
                },
            ],
        )

    return None


def verify(
    path: str | Path = ".",
    *,
    ref: str | None = None,
    uncommitted: bool = True,
    staged_only: bool = False,
    fail_on: str = "high",
    baseline: str | None = None,
    scope_files: list[str] | None = None,
    response_profile: str | None = None,
) -> dict[str, Any]:
    """Run post-edit verification and return a binary pass/fail verdict.

    Wraps ``shadow_verify()`` and applies a severity-threshold gate to
    produce a single boolean ``pass`` field suitable for CI exit codes.

    Parameters
    ----------
    path:
        Repository root directory.
    ref:
        Git ref to compare against (unused by shadow_verify directly,
        reserved for future diff-based verify).
    uncommitted:
        Analyze working-tree changes vs HEAD.
    staged_only:
        Analyze only staged changes (mutually exclusive with uncommitted).
    fail_on:
        Severity threshold — findings at or above this level cause FAIL.
        One of: critical, high, medium, low, none.
    baseline:
        Path to a ``.drift-baseline.json`` file for fingerprint comparison.
    scope_files:
        List of posix-relative file paths to restrict the verification scope.
    response_profile:
        Optional profile to compact the response payload.

    Returns
    -------
    dict
        ``pass``                 — True when no blocking reasons exist.
        ``blocking_reasons``     — Structured list of reasons for failure.
        ``findings_introduced``  — New findings since reference (concise).
        ``findings_resolved``    — Resolved findings since reference (concise).
        ``score_before``         — Score before edit.
        ``score_after``          — Score after edit.
        ``score_delta``          — Score difference (positive = regression).
        ``direction``            — improving/stable/degrading.
        ``agent_instruction``    — Natural-language guidance.
        ``next_tool_call``       — ADR-024 next-step contract.
    """
    start_ms = _time.monotonic()
    repo_path = Path(path).resolve()

    params: dict[str, Any] = {
        "path": str(path),
        "ref": ref,
        "uncommitted": uncommitted,
        "staged_only": staged_only,
        "fail_on": fail_on,
        "baseline": baseline,
        "scope_files": scope_files or [],
    }

    def elapsed_ms() -> int:
        return int((_time.monotonic() - start_ms) * 1_000)

    try:
        validation_error = _validate_verify_modes(
            ref=ref,
            uncommitted=uncommitted,
            staged_only=staged_only,
            baseline=baseline,
        )
        if validation_error is not None:
            _emit_api_telemetry(
                tool_name="api.verify",
                params=params,
                status="ok",
                elapsed_ms=elapsed_ms(),
                result=validation_error,
                error=None,
                repo_root=repo_path,
            )
            return validation_error

        use_diff_semantics = bool(ref or baseline or staged_only)

        if use_diff_semantics:
            compare = diff_api(
                path=path,
                diff_ref=ref or "HEAD~1",
                uncommitted=uncommitted,
                staged_only=staged_only,
                baseline_file=baseline,
                response_detail="concise",
                response_profile=None,
            )
            if compare.get("type") == "error":
                _emit_api_telemetry(
                    tool_name="api.verify",
                    params=params,
                    status="error",
                    elapsed_ms=elapsed_ms(),
                    result=compare,
                    error=None,
                    repo_root=repo_path,
                )
                return compare

            delta = float(compare.get("delta", 0.0))
            new_findings = compare.get("new_findings", [])
            resolved_findings = compare.get("resolved_findings", [])
            score_before = float(compare.get("score_before", 0.0))
            score_after = float(compare.get("score_after", 0.0))
        else:
            # Default mode keeps shadow_verify semantics for cross-file checks.
            sv_result = shadow_verify(
                path=path,
                scope_files=scope_files,
                uncommitted=uncommitted,
            )

            if sv_result.get("type") == "error":
                _emit_api_telemetry(
                    tool_name="api.verify",
                    params=params,
                    status="error",
                    elapsed_ms=elapsed_ms(),
                    result=sv_result,
                    error=None,
                    repo_root=repo_path,
                )
                return sv_result

            delta = float(sv_result.get("delta", 0.0))
            new_findings = sv_result.get("new_findings_in_scope", [])
            resolved_findings = sv_result.get("resolved_findings_in_scope", [])

            score_after = float(sv_result.get("score_after", 0.0))
            score_before = round(score_after - delta, 4)

        # Apply severity gate to new findings.
        severity_order = ["critical", "high", "medium", "low", "info"]
        fail_on_lower = fail_on.lower() if fail_on else "high"

        if fail_on_lower == "none":
            threshold_idx = len(severity_order)  # nothing blocks
        else:
            threshold_idx = (
                severity_order.index(fail_on_lower)
                if fail_on_lower in severity_order
                else 1  # default to high
            )

        # Build blocking reasons.
        blocking_reasons: list[dict[str, Any]] = []

        # 1. Score degradation blocks.
        if delta > 0.001:
            blocking_reasons.append({
                "type": "score_degradation",
                "reason": f"Score degraded by {delta:+.4f}",
                "delta": delta,
            })

        # 2. New findings above threshold block.
        for finding in new_findings:
            finding_sev = finding.get("severity", "info").lower()
            if finding_sev in severity_order:
                finding_idx = severity_order.index(finding_sev)
                if finding_idx <= threshold_idx:
                    blocking_reasons.append({
                        "type": "finding_above_threshold",
                        "reason": (
                            f"{finding_sev.upper()} finding: "
                            f"{finding.get('title', 'unknown')}"
                        ),
                        "signal": finding.get("signal", ""),
                        "file": finding.get("file", ""),
                        "severity": finding_sev,
                        "title": finding.get("title", ""),
                    })

        passed = len(blocking_reasons) == 0
        direction = _direction_from_delta(delta)

        agent_instruction = _verify_agent_instruction(
            passed=passed,
            blocking_reasons=blocking_reasons,
        )

        if passed:
            next_contract = _next_step_contract(
                next_tool=None,
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
            "type": "verify",
            "pass": passed,
            "blocking_reasons": blocking_reasons,
            "findings_introduced": new_findings,
            "findings_resolved": resolved_findings,
            "findings_introduced_count": len(new_findings),
            "findings_resolved_count": len(resolved_findings),
            "score_before": score_before,
            "score_after": score_after,
            "score_delta": delta,
            "direction": direction,
            "ref": ref or "HEAD",
            "scope_files": sorted(scope_files) if scope_files else [],
            "agent_instruction": agent_instruction,
        } | next_contract

        _emit_api_telemetry(
            tool_name="api.verify",
            params=params,
            status="ok",
            elapsed_ms=elapsed_ms(),
            result=resp,
            error=None,
            repo_root=repo_path,
        )
        return shape_for_profile(resp, response_profile)

    except Exception as exc:  # noqa: BLE001
        _log.exception("verify failed: %s", exc)
        _emit_api_telemetry(
            tool_name="api.verify",
            params=params,
            status="error",
            elapsed_ms=elapsed_ms(),
            result=None,
            error=exc,
            repo_root=repo_path,
        )
        return _error_response(
            "verify_failed",
            f"verify encountered an unexpected error: {exc}",
            recoverable=True,
            recovery_tool_call={"tool": "drift_scan", "params": {"path": str(path)}},
        )

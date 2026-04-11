"""Diff endpoint — analyze drift changes since a git ref or baseline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from drift.api._config import (
    _emit_api_telemetry,
    _load_config_cached,
    _warn_config_issues,
)
from drift.api_helpers import (
    DONE_ACCEPT_CHANGE,
    DONE_STAGED_EXISTS,
    _base_response,
    _error_response,
    _finding_concise,
    _finding_detailed,
    _next_step_contract,
    shape_for_profile,
    signal_abbrev,
)


def _diff_decision_reason(
    *,
    accept_change: bool,
    in_scope_accept: bool,
    has_out_of_scope_noise: bool,
) -> tuple[str, str]:
    """Return a stable code/text reason for the diff decision.

    This gives agents a single unambiguous explanation for accept/reject,
    instead of requiring interpretation of multiple boolean fields.
    """
    if accept_change:
        return (
            "accepted_no_blockers",
            "Accepted: no in-scope blockers detected.",
        )
    if not in_scope_accept:
        return (
            "rejected_in_scope_blockers",
            "Rejected due to in-scope high findings or score regression.",
        )
    if has_out_of_scope_noise:
        return (
            "rejected_out_of_scope_noise_only",
            "Rejected due to out-of-scope noise only.",
        )
    return (
        "rejected_unknown",
        "Rejected: blocking conditions detected.",
    )


def diff(
    path: str | Path = ".",
    *,
    diff_ref: str = "HEAD~1",
    uncommitted: bool = False,
    staged_only: bool = False,
    baseline_file: str | None = None,
    target_path: str | None = None,
    max_findings: int = 10,
    response_detail: str = "concise",
    signals: list[str] | None = None,
    exclude_signals: list[str] | None = None,
    response_profile: str | None = None,
) -> dict[str, Any]:
    """Analyze drift changes since a git ref or baseline.

    Parameters
    ----------
    path:
        Repository root directory.
    diff_ref:
        Git ref to diff against (e.g. ``"HEAD~1"``, ``"main"``).
    uncommitted:
        Compare current working tree changes against ``HEAD``.
    staged_only:
        Compare only staged changes.
    baseline_file:
        Path to a ``.drift-baseline.json`` file for comparison.
    target_path:
        Restrict decision logic to findings inside this subpath while still
        reporting whether out-of-scope diff noise exists.
    max_findings:
        Maximum findings in the response.
    response_detail:
        ``"concise"`` or ``"detailed"``.
    """
    from drift.analyzer import analyze_diff as _analyze_diff
    from drift.telemetry import timed_call

    repo_path = Path(path).resolve()
    elapsed_ms = timed_call()
    params = {
        "path": str(path),
        "diff_ref": diff_ref,
        "uncommitted": uncommitted,
        "staged_only": staged_only,
        "baseline_file": baseline_file,
        "target_path": target_path,
        "max_findings": max_findings,
        "response_detail": response_detail,
        "signals": signals,
        "exclude_signals": exclude_signals,
    }

    try:
        cfg = _load_config_cached(repo_path)
        _warn_config_issues(cfg)

        if uncommitted and staged_only:
            raise ValueError("Options 'uncommitted' and 'staged_only' are mutually exclusive.")

        if not uncommitted and not staged_only and diff_ref.startswith("--"):
            result = _error_response(
                "DRIFT-1003",
                f"Invalid diff_ref value: '{diff_ref}' looks like a command-line option.",
                invalid_fields=[{
                    "field": "diff_ref",
                    "value": diff_ref,
                    "reason": (
                        "Must be a valid git ref (e.g. HEAD~1, main, a1b2c3d),"
                        " not an option flag"
                    ),
                }],
                suggested_fix={
                    "action": "Pass a valid git ref",
                    "example_call": {"tool": "drift_diff", "params": {"diff_ref": "HEAD~1"}},
                },
            )
            _emit_api_telemetry(
                tool_name="api.diff",
                params=params,
                status="ok",
                elapsed_ms=elapsed_ms(),
                result=result,
                error=None,
                repo_root=repo_path,
            )
            return result

        diff_mode = "ref"
        if staged_only:
            diff_mode = "staged"
            diff_ref = "HEAD"
        elif uncommitted:
            diff_mode = "uncommitted"
            diff_ref = "HEAD"

        # Current analysis (diff scope)
        diff_analysis = _analyze_diff(
            repo_path,
            config=cfg,
            diff_ref=diff_ref,
            diff_mode=diff_mode,
        )

        # Baseline comparison
        if baseline_file:
            bl_path = Path(baseline_file).resolve()
            if not bl_path.is_relative_to(repo_path):
                result = _error_response(
                    "DRIFT-1003",
                    "baseline_file must reside inside the repository root.",
                    invalid_fields=[{
                        "field": "baseline_file",
                        "value": baseline_file,
                        "reason": "Path traversal outside repository root",
                    }],
                )
                _emit_api_telemetry(
                    tool_name="api.diff",
                    params=params,
                    status="ok",
                    elapsed_ms=elapsed_ms(),
                    result=result,
                    error=None,
                    repo_root=repo_path,
                )
                return result

            from drift.baseline import baseline_diff as _bl_diff
            from drift.baseline import load_baseline

            fps = load_baseline(bl_path)
            new, _known = _bl_diff(diff_analysis.findings, fps)
            resolved = [f for f in _known]
        else:
            new = diff_analysis.findings
            resolved = []

        # Signal filter: include/exclude by signal abbreviation
        if signals:
            _incl = {s.upper() for s in signals}
            new = [f for f in new if signal_abbrev(f.signal_type) in _incl]
            resolved = [f for f in resolved if signal_abbrev(f.signal_type) in _incl]
        if exclude_signals:
            _excl = {s.upper() for s in exclude_signals}
            new = [f for f in new if signal_abbrev(f.signal_type) not in _excl]
            resolved = [f for f in resolved if signal_abbrev(f.signal_type) not in _excl]

        scoped_new = new
        scoped_resolved = resolved
        out_of_scope_new = []
        normalized_target: str | None = None
        if target_path:
            normalized_target = Path(target_path).as_posix().strip("/")

            def _in_scope(finding: Any) -> bool:
                raw_file_path = getattr(finding, "file_path", None)
                if raw_file_path is None or not normalized_target:
                    return False
                file_path = Path(raw_file_path).as_posix().strip("/")
                return bool(
                    file_path == normalized_target
                    or file_path.startswith(
                    normalized_target + "/"
                )
                )

            scoped_new = [finding for finding in new if _in_scope(finding)]
            scoped_resolved = [finding for finding in resolved if _in_scope(finding)]
            out_of_scope_new = [finding for finding in new if not _in_scope(finding)]

        # Score comparison via trend context
        score_after = diff_analysis.drift_score
        score_before: float = 0.0
        if (
            diff_analysis.trend is not None
            and diff_analysis.trend.previous_score is not None
        ):
            score_before = diff_analysis.trend.previous_score
            has_trend_baseline = True
        else:
            has_trend_baseline = False
        delta = round(score_after - score_before, 4)

        # When no historical baseline exists, flag the score fields as
        # synthetic so agents don't misinterpret zero as the repo baseline (#119).
        score_basis = "historical" if has_trend_baseline else "zero_default"

        from drift.output.json_output import _priority_class

        drift_categories = sorted({_priority_class(f) for f in scoped_new}) if scoped_new else []
        affected = sorted({
            f.file_path.as_posix().rsplit("/", 1)[0]
            for f in scoped_new
            if f.file_path
        })

        status = "stable"
        if delta > 0.01:
            status = "new_critical" if any(
                f.severity.value in ("critical", "high") for f in scoped_new
            ) else "degraded"
        elif delta < -0.01:
            status = "improved"

        confidence = "high"
        if diff_analysis.is_degraded:
            confidence = "low"
        elif diff_analysis.total_files < 5:
            confidence = "medium"

        if response_detail == "concise":
            ranked_new = sorted(scoped_new, key=lambda f: f.impact, reverse=True)[:max_findings]
            new_list = [_finding_concise(f) for f in ranked_new]
            resolved_list = [_finding_concise(f) for f in scoped_resolved[:max_findings]]
        else:
            ranked_new = sorted(scoped_new, key=lambda f: f.impact, reverse=True)[:max_findings]
            new_list = [_finding_detailed(f) for f in ranked_new]
            resolved_list = [_finding_detailed(f) for f in scoped_resolved[:max_findings]]

        n_new = len(scoped_new)
        summary_parts = [f"{n_new} new finding{'s' if n_new != 1 else ''}"]
        high_count = sum(
            1 for f in scoped_new if f.severity.value in ("critical", "high")
        )
        if high_count:
            summary_parts.append(f"{high_count} high/critical")
        if out_of_scope_new:
            summary_parts.append(f"{len(out_of_scope_new)} out-of-scope")
        summary_parts.append(f"drift score {'+' if delta >= 0 else ''}{delta:.3f}")

        # Compute in-scope-only accept decision (D6: helps agents isolate
        # scoped results from pre-existing out-of-scope noise).
        in_scope_blocking: list[str] = []
        if high_count:
            in_scope_blocking.append("new_high_or_critical_findings")
        if delta > 0.0:
            in_scope_blocking.append("drift_score_regressed")

        blocking_reasons: list[str] = list(in_scope_blocking)
        if out_of_scope_new:
            blocking_reasons.append("out_of_scope_diff_noise")

        # Resolved-count-by-rule: helps agents gauge batch fix efficiency
        _resolved_by_rule: dict[str, int] = {}
        for _rf in scoped_resolved:
            _rk = signal_abbrev(_rf.signal_type)
            _resolved_by_rule[_rk] = _resolved_by_rule.get(_rk, 0) + 1

        # Noise context: help agents distinguish pre-existing findings from
        # change-caused findings when drift_detected=false but counts > 0.
        pre_existing_count = len(out_of_scope_new)
        noise_explanation = None
        if not baseline_file and pre_existing_count > 0:
            noise_explanation = (
                f"{pre_existing_count} finding(s) are pre-existing out-of-scope noise, "
                f"not caused by this change. Use 'drift baseline save' then "
                f"'drift diff --baseline .drift-baseline.json' to suppress them."
            )
        elif not scoped_new and not out_of_scope_new:
            noise_explanation = "No new findings detected."
        noise_context = {
            "pre_existing_count": pre_existing_count,
            "explanation": noise_explanation,
        }

        thresholds = getattr(cfg, "thresholds", None)
        max_changed_files = getattr(
            thresholds,
            "diff_baseline_recommend_max_changed_files",
            50,
        )
        max_new_findings = getattr(
            thresholds,
            "diff_baseline_recommend_max_new_findings",
            100,
        )
        max_out_of_scope_findings = getattr(
            thresholds,
            "diff_baseline_recommend_max_out_of_scope_findings",
            50,
        )

        baseline_reasons: list[str] = []
        if not baseline_file:
            if diff_analysis.total_files >= max_changed_files:
                baseline_reasons.append("large_working_tree")
            if n_new >= max_new_findings:
                baseline_reasons.append("high_new_finding_volume")
            if (
                target_path
                and len(out_of_scope_new)
                >= max_out_of_scope_findings
            ):
                baseline_reasons.append("out_of_scope_noise")

        baseline_recommended = bool(baseline_reasons)
        baseline_reason = baseline_reasons[0] if baseline_reasons else "none"

        accept_change = not blocking_reasons
        in_scope_accept = not in_scope_blocking
        decision_reason_code, decision_reason = _diff_decision_reason(
            accept_change=accept_change,
            in_scope_accept=in_scope_accept,
            has_out_of_scope_noise=bool(out_of_scope_new),
        )

        staged_file_count = diff_analysis.total_files if diff_mode == "staged" else None
        no_staged_files = bool(diff_mode == "staged" and diff_analysis.total_files == 0)

        if not accept_change:
            if decision_reason_code == "rejected_out_of_scope_noise_only":
                _agent_hint = (
                    "No in-scope blockers detected, but out-of-scope drift noise "
                    "is present. Use in_scope_accept for scoped gating and "
                    "consider creating or refreshing a baseline."
                )
            else:
                _agent_hint = (
                    "Change rejected due to in-scope drift blockers. Call "
                    "drift_fix_plan and address blockers before proceeding."
                )
        elif no_staged_files:
            _agent_hint = (
                "No staged files were analyzed (staged_file_count=0). "
                "Stage changes before relying on accept_change."
            )
        elif status == "improved":
            _agent_hint = (
                "Score is improving. Continue with the next batch_eligible "
                "group or next fix_plan task. Use drift_nudge between edits "
                "for fast feedback."
            )
        elif len(scoped_new) > 0:
            _agent_hint = (
                "New findings exist but are within acceptance threshold. "
                "Review the new_findings list before proceeding to ensure "
                "they are acceptable."
            )
        else:
            _agent_hint = (
                "No drift change detected. Safe to proceed to the next task."
            )
        # Suggested next batch targets: signals with remaining new findings
        _new_by_signal: dict[str, int] = {}
        for _nf in scoped_new:
            _nk = signal_abbrev(_nf.signal_type)
            _new_by_signal[_nk] = _new_by_signal.get(_nk, 0) + 1
        _batch_targets = [
            {"signal": sig, "remaining": cnt}
            for sig, cnt in sorted(_new_by_signal.items(), key=lambda x: -x[1])
        ]

        result = _base_response(
            drift_detected=delta > 0.0,
            status=status,
            severity=diff_analysis.severity.value,
            score_before=round(score_before, 4),
            score_after=round(score_after, 4),
            delta=delta,
            score_basis=score_basis,
            score_regressed=delta > 0.0,
            confidence=confidence,
            diff_ref=diff_ref,
            diff_mode=diff_mode,
            staged_file_count=staged_file_count,
            no_staged_files=no_staged_files,
            target_path=normalized_target,
            new_findings=new_list,
            resolved_findings=resolved_list,
            new_finding_count=len(scoped_new),
            new_high_or_critical=high_count,
            resolved_count=len(scoped_resolved),
            resolved_count_by_rule=_resolved_by_rule,
            out_of_scope_new_count=len(out_of_scope_new),
            noise_context=noise_context,
            baseline_recommended=baseline_recommended,
            baseline_reason=baseline_reason,
            drift_categories=drift_categories,
            affected_components=affected,
            summary=", ".join(summary_parts),
            accept_change=accept_change,
            in_scope_accept=in_scope_accept,
            blocking_reasons=blocking_reasons,
            decision_reason_code=decision_reason_code,
            decision_reason=decision_reason,
            suggested_next_batch_targets=_batch_targets,
            recommended_next_actions=_diff_next_actions(
                scoped_new, status, blocking_reasons,
                in_scope_accept=in_scope_accept,
                has_baseline=baseline_file is not None,
                baseline_recommended=baseline_recommended,
                baseline_reason=baseline_reason,
            ),
            response_truncated=len(scoped_new) > max_findings,
            agent_instruction=_agent_hint,
        )
        result.update(_diff_next_step_contract(
            status=status,
            accept_change=accept_change,
            no_staged_files=no_staged_files,
            decision_reason_code=decision_reason_code,
            batch_targets=_batch_targets,
        ))
        _emit_api_telemetry(
            tool_name="api.diff",
            params=params,
            status="ok",
            elapsed_ms=elapsed_ms(),
            result=result,
            error=None,
            repo_root=repo_path,
        )
        return shape_for_profile(result, response_profile)
    except Exception as exc:
        _emit_api_telemetry(
            tool_name="api.diff",
            params=params,
            status="error",
            elapsed_ms=elapsed_ms(),
            result=None,
            error=exc,
            repo_root=repo_path,
        )
        raise


def _diff_next_actions(
    new_findings: list,
    status: str,
    blocking_reasons: list[str],
    *,
    in_scope_accept: bool = False,
    has_baseline: bool = False,
    baseline_recommended: bool = False,
    baseline_reason: str = "none",
) -> list[str]:
    """Derive next actions from diff results."""
    actions: list[str] = []
    if status in ("degraded", "new_critical"):
        actions.append("drift_fix_plan for new findings")
    if any(f.severity.value in ("critical", "high") for f in new_findings):
        actions.append("drift_explain for high-severity signals")
    if baseline_recommended and not has_baseline:
        actions.append(
            "Run 'drift baseline save' before retrying diff "
            f"(baseline_reason={baseline_reason})"
        )
    if "out_of_scope_diff_noise" in blocking_reasons and not has_baseline:
        actions.append(
            "Use 'drift baseline save' then 'drift diff --baseline "
            ".drift-baseline.json' to suppress pre-existing noise"
        )
    if "out_of_scope_diff_noise" in blocking_reasons and in_scope_accept:
        actions.append(
            "accept_change is false due to out-of-scope noise only — "
            "use in_scope_accept (true) as the scoped gate decision"
        )
    elif "out_of_scope_diff_noise" in blocking_reasons:
        actions.append(
            "out_of_scope_diff_noise is pre-existing — check in_scope_accept "
            "for the scoped decision; use 'drift diff --diff-ref HEAD' for "
            "uncommitted changes"
        )
    if status == "improved":
        actions.append("No action needed — drift is improving")
    return actions or ["No immediate action required"]


def _diff_next_step_contract(
    *,
    status: str,
    accept_change: bool,
    no_staged_files: bool,
    decision_reason_code: str,
    batch_targets: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the next-step contract for diff responses (ADR-024)."""
    if no_staged_files:
        return _next_step_contract(next_tool=None, done_when=DONE_STAGED_EXISTS)
    if accept_change and status == "improved" and batch_targets:
        top = batch_targets[0]
        return _next_step_contract(
            next_tool="drift_fix_plan",
            next_params={"signal": top["signal"]},
            done_when=DONE_ACCEPT_CHANGE,
        )
    if accept_change:
        return _next_step_contract(next_tool=None, done_when=DONE_ACCEPT_CHANGE)
    if decision_reason_code == "rejected_out_of_scope_noise_only":
        return _next_step_contract(
            next_tool="drift_diff",
            next_params={"uncommitted": True, "baseline_file": ".drift-baseline.json"},
            done_when=DONE_ACCEPT_CHANGE,
            fallback_tool="drift_scan",
            fallback_params={"response_detail": "concise"},
        )
    # degraded / new_critical / rejected
    return _next_step_contract(
        next_tool="drift_fix_plan",
        next_params={},
        done_when=DONE_ACCEPT_CHANGE,
        fallback_tool="drift_scan",
        fallback_params={"response_detail": "concise"},
    )

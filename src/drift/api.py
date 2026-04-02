"""Programmatic API for drift analysis — agent-native, JSON-first.

This module provides the formalized public interface consumed by both the
MCP server and the CLI.  All functions return typed result dicts (not raw
``RepoAnalysis`` objects) so callers always receive a stable, serialisable
contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from drift.api_helpers import (
    VALID_SIGNAL_IDS,
    _base_response,
    _error_response,
    _finding_concise,
    _finding_detailed,
    _fix_first_concise,
    _task_to_api_dict,
    _top_signals,
    _trend_dict,
    resolve_signal,
    signal_abbrev,
)

if TYPE_CHECKING:
    from drift.incremental import BaselineSnapshot
    from drift.models import Finding, ParseResult, RepoAnalysis


def _emit_api_telemetry(
    *,
    tool_name: str,
    params: dict[str, Any],
    status: str,
    elapsed_ms: int,
    result: dict[str, Any] | None,
    error: Exception | None,
    repo_root: Path | None,
) -> None:
    """Emit non-blocking telemetry for API calls."""
    from drift.telemetry import log_tool_event

    log_tool_event(
        tool_name=tool_name,
        params=params,
        status=status,
        duration_ms=elapsed_ms,
        result=result,
        error=str(error) if error else None,
        repo_root=repo_root,
    )




# ---------------------------------------------------------------------------
# Core API functions
# ---------------------------------------------------------------------------


def scan(
    path: str | Path = ".",
    *,
    target_path: str | None = None,
    since_days: int = 90,
    signals: list[str] | None = None,
    max_findings: int = 10,
    response_detail: str = "concise",
    strategy: str = "diverse",
) -> dict[str, Any]:
    """Run full drift analysis and return a structured result dict.

    Parameters
    ----------
    path:
        Repository root directory.
    target_path:
        Restrict analysis to a subdirectory.
    since_days:
        Days of git history to consider.
    signals:
        Optional list of signal abbreviations to include (e.g. ``["PFS", "AVS"]``).
    max_findings:
        Maximum number of findings in the response.
    response_detail:
        ``"concise"`` (token-sparing) or ``"detailed"`` (full fields).
    strategy:
        ``"diverse"`` (default) or ``"top-severity"`` (pure score sort).
    """
    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig, apply_signal_filter
    from drift.telemetry import timed_call

    repo_path = Path(path).resolve()
    elapsed_ms = timed_call()
    params = {
        "path": str(path),
        "target_path": target_path,
        "since_days": since_days,
        "signals": signals,
        "max_findings": max_findings,
        "response_detail": response_detail,
        "strategy": strategy,
    }

    try:
        cfg = DriftConfig.load(repo_path)

        # Validate target_path existence
        warnings: list[str] = []
        if target_path and not (repo_path / target_path).exists():
            warnings.append(
                f"target_path '{target_path}' does not exist in repository"
            )

        if signals:
            select_csv = ",".join(signals)
            apply_signal_filter(cfg, select_csv, None)

        analysis = analyze_repo(
            repo_path,
            config=cfg,
            since_days=since_days,
            target_path=target_path,
        )
        result = _format_scan_response(
            analysis,
            max_findings=max_findings,
            detail=response_detail,
            strategy=strategy,
            signal_filter=set(s.upper() for s in signals) if signals else None,
        )
        if warnings:
            result["warnings"] = warnings
        _emit_api_telemetry(
            tool_name="api.scan",
            params=params,
            status="ok",
            elapsed_ms=elapsed_ms(),
            result=result,
            error=None,
            repo_root=repo_path,
        )
        return result
    except Exception as exc:
        _emit_api_telemetry(
            tool_name="api.scan",
            params=params,
            status="error",
            elapsed_ms=elapsed_ms(),
            result=None,
            error=exc,
            repo_root=repo_path,
        )
        raise


def _diverse_findings(findings: list, max_findings: int) -> list:
    """Select findings with signal diversity.

    Algorithm:
    1. One top finding per signal with score >= 0.5 (sorted by score desc)
    2. Fill remaining slots with highest-scored remaining findings
    """
    by_score = sorted(findings, key=lambda f: f.impact, reverse=True)

    # Phase 1: one top finding per signal (score >= 0.5)
    seen_signals: set[str] = set()
    phase1: list = []
    phase1_set: set[int] = set()
    for f in by_score:
        sig = f.signal_type.value
        if sig not in seen_signals and f.score >= 0.5:
            seen_signals.add(sig)
            phase1.append(f)
            phase1_set.add(id(f))

    # Phase 2: fill remaining slots from highest-scored remaining
    remaining = [f for f in by_score if id(f) not in phase1_set]
    budget = max_findings - len(phase1)
    result = phase1 + remaining[:budget] if budget > 0 else phase1[:max_findings]
    return result


def _format_scan_response(
    analysis: RepoAnalysis,
    *,
    max_findings: int = 10,
    detail: str = "concise",
    strategy: str = "diverse",
    signal_filter: set[str] | None = None,
) -> dict[str, Any]:
    """Format a RepoAnalysis into the scan response schema."""
    selected_findings = analysis.findings
    if signal_filter:
        selected_findings = [
            f for f in analysis.findings
            if signal_abbrev(f.signal_type) in signal_filter
        ]

    if strategy == "diverse":
        limited = _diverse_findings(selected_findings, max_findings)
    else:
        ranked = sorted(
            selected_findings, key=lambda f: f.impact, reverse=True,
        )
        limited = ranked[:max_findings]
    critical_count = sum(1 for f in selected_findings if f.severity.value == "critical")
    high_count = sum(1 for f in selected_findings if f.severity.value == "high")
    blocking_reasons: list[str] = []
    if critical_count or high_count:
        blocking_reasons.append("existing_high_or_critical_findings")
    if analysis.trend and analysis.trend.direction == "degrading":
        blocking_reasons.append("drift_trend_degrading")

    if detail == "concise":
        findings_list = [_finding_concise(f) for f in limited]
    else:
        findings_list = [_finding_detailed(f, rank=i + 1) for i, f in enumerate(limited)]

    result = _base_response(
        drift_score=round(analysis.drift_score, 4),
        severity=analysis.severity.value,
        total_files=analysis.total_files,
        total_functions=analysis.total_functions,
        ai_ratio=round(analysis.ai_attributed_ratio, 3),
        trend=_trend_dict(analysis),
        top_signals=_top_signals(analysis, signal_filter=signal_filter),
        fix_first=_fix_first_concise(
            cast("RepoAnalysis", SimpleNamespace(findings=selected_findings)),
            max_items=min(max_findings, 5),
        ),
        finding_count=len(selected_findings),
        critical_count=critical_count,
        high_count=high_count,
        findings_returned=len(limited),
        findings=findings_list,
        accept_change=not blocking_reasons,
        blocking_reasons=blocking_reasons,
        response_truncated=len(selected_findings) > max_findings,
        recommended_next_actions=_scan_next_actions(
            analysis,
            findings=selected_findings,
        ),
        agent_instruction=(
            "Use drift_fix_plan to get prioritised repair tasks. "
            "After each file change, call drift_diff(uncommitted=True) "
            "to verify improvement before proceeding."
        ),
    )
    if getattr(analysis, "skipped_files", 0) > 0:
        result["skipped_files"] = analysis.skipped_files
        result["skipped_languages"] = sorted(analysis.skipped_languages.keys())
    return result

def _scan_next_actions(
    analysis: RepoAnalysis,
    *,
    findings: list | None = None,
) -> list[str]:
    """Derive recommended tool calls from scan results."""
    scoped_findings = findings if findings is not None else analysis.findings
    actions: list[str] = []
    high_critical = sum(
        1 for f in scoped_findings
        if f.severity.value in ("critical", "high")
    )
    if scoped_findings:
        actions.append("drift_fix_plan for top-priority findings")
    if high_critical:
        actions.append("drift_explain for unfamiliar high-severity signals")
    if high_critical > 20:
        actions.append(
            "Many pre-existing findings — use 'drift baseline save' then "
            "'drift diff --baseline .drift-baseline.json' to focus on new changes only"
        )
    if analysis.trend and analysis.trend.direction == "degrading":
        actions.append("drift_diff to identify recent regressions")
    return actions or ["No immediate action required"]


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
    from drift.config import DriftConfig
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
    }

    try:
        cfg = DriftConfig.load(repo_path)

        if uncommitted and staged_only:
            raise ValueError("Options 'uncommitted' and 'staged_only' are mutually exclusive.")

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
            from drift.baseline import baseline_diff as _bl_diff
            from drift.baseline import load_baseline

            fps = load_baseline(Path(baseline_file))
            new, _known = _bl_diff(diff_analysis.findings, fps)
            resolved = [f for f in _known]
        else:
            new = diff_analysis.findings
            resolved = []

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
        score_before = (
            diff_analysis.trend.previous_score
            if diff_analysis.trend and diff_analysis.trend.previous_score is not None
            else 0.0
        )
        delta = round(score_after - score_before, 4)

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
        elif status == "improved":
            _agent_hint = "Score is improving. Safe to continue with next task."
        else:
            _agent_hint = "No drift change detected. Safe to proceed."
        result = _base_response(
            drift_detected=delta > 0.0,
            status=status,
            severity=diff_analysis.severity.value,
            score_before=round(score_before, 4),
            score_after=round(score_after, 4),
            delta=delta,
            score_regressed=delta > 0.0,
            confidence=confidence,
            diff_ref=diff_ref,
            diff_mode=diff_mode,
            target_path=normalized_target,
            new_findings=new_list,
            resolved_findings=resolved_list,
            new_finding_count=len(scoped_new),
            new_high_or_critical=high_count,
            resolved_count=len(scoped_resolved),
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


def explain(topic: str) -> dict[str, Any]:
    """Explain a signal, rule, or error code.

    Parameters
    ----------
    topic:
        A signal abbreviation (``"PFS"``), signal type name
        (``"pattern_fragmentation"``), or error code (``"DRIFT-1001"``).
    """
    from drift.commands.explain import _SIGNAL_INFO
    from drift.telemetry import timed_call

    elapsed_ms = timed_call()
    params = {"topic": topic}

    try:
        # Try as signal abbreviation first
        upper = topic.upper()
        if upper in _SIGNAL_INFO:
            info = _SIGNAL_INFO[upper]
            result = _base_response(
                type="signal",
                signal=upper,
                name=info.get("name", upper),
                weight=float(info.get("weight", "0")),
                description=info.get("description", ""),
                detection_logic=info.get("detects", ""),
                typical_cause="Multiple AI sessions or copy-paste-modify patterns.",
                remediation_approach=info.get("fix_hint", ""),
                related_signals=_related_signals(upper),
            )
            _emit_api_telemetry(
                tool_name="api.explain",
                params=params,
                status="ok",
                elapsed_ms=elapsed_ms(),
                result=result,
                error=None,
                repo_root=Path.cwd(),
            )
            return result

        # Try as SignalType value
        resolved = resolve_signal(topic)
        if resolved:
            abbr = signal_abbrev(resolved)
            if abbr in _SIGNAL_INFO:
                result = explain(abbr)
                _emit_api_telemetry(
                    tool_name="api.explain",
                    params=params,
                    status="ok",
                    elapsed_ms=elapsed_ms(),
                    result=result,
                    error=None,
                    repo_root=Path.cwd(),
                )
                return result
            result = _base_response(
                type="signal",
                signal=abbr,
                name=resolved.value,
                description=f"Signal: {resolved.value}",
            )
            _emit_api_telemetry(
                tool_name="api.explain",
                params=params,
                status="ok",
                elapsed_ms=elapsed_ms(),
                result=result,
                error=None,
                repo_root=Path.cwd(),
            )
            return result

        # Try as error code
        from drift.errors import ERROR_REGISTRY

        if topic.upper() in ERROR_REGISTRY:
            err = ERROR_REGISTRY[topic.upper()]
            result = _base_response(
                type="error_code",
                error_code=err.code,
                category=err.category,
                summary=err.summary,
                why=err.why,
                action=err.action,
            )
            _emit_api_telemetry(
                tool_name="api.explain",
                params=params,
                status="ok",
                elapsed_ms=elapsed_ms(),
                result=result,
                error=None,
                repo_root=Path.cwd(),
            )
            return result

        # Not found — helpful error
        result = _error_response(
            "DRIFT-1003",
            f"Unknown topic: '{topic}'",
            invalid_fields=[{
                "field": "topic", "value": topic,
                "reason": "Not a valid signal, rule, or error code",
            }],
            suggested_fix={
                "action": "Use a valid signal abbreviation or error code",
                "valid_values": VALID_SIGNAL_IDS,
                "example_call": {"tool": "drift_explain", "params": {"topic": "PFS"}},
            },
        )
        _emit_api_telemetry(
            tool_name="api.explain",
            params=params,
            status="ok",
            elapsed_ms=elapsed_ms(),
            result=result,
            error=None,
            repo_root=Path.cwd(),
        )
        return result
    except Exception as exc:
        _emit_api_telemetry(
            tool_name="api.explain",
            params=params,
            status="error",
            elapsed_ms=elapsed_ms(),
            result=None,
            error=exc,
            repo_root=Path.cwd(),
        )
        raise


def _related_signals(abbr: str) -> list[str]:
    """Return related signal abbreviations."""
    relations: dict[str, list[str]] = {
        "PFS": ["MDS"],
        "MDS": ["PFS"],
        "AVS": ["CCC", "COD"],
        "CCC": ["AVS"],
        "COD": ["AVS", "CCC"],
        "EDS": ["BEM"],
        "BEM": ["EDS"],
        "TVS": ["ECM"],
        "ECM": ["TVS"],
    }
    return relations.get(abbr, [])


def fix_plan(
    path: str | Path = ".",
    *,
    finding_id: str | None = None,
    signal: str | None = None,
    max_tasks: int = 5,
    automation_fit_min: str | None = None,
    target_path: str | None = None,
) -> dict[str, Any]:
    """Generate a prioritized fix plan with constraints and success criteria.

    Parameters
    ----------
    path:
        Repository root directory.
    finding_id:
        Target a specific finding by its task ID.
    signal:
        Filter to findings of this signal (abbreviation or full name).
    max_tasks:
        Maximum tasks to return.
    automation_fit_min:
        Minimum automation fitness level: ``"low"``, ``"medium"``, or ``"high"``.
    target_path:
        Restrict tasks to findings inside this subpath.
    """
    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig
    from drift.output.agent_tasks import analysis_to_agent_tasks
    from drift.telemetry import timed_call

    repo_path = Path(path).resolve()
    elapsed_ms = timed_call()
    params = {
        "path": str(path),
        "finding_id": finding_id,
        "signal": signal,
        "max_tasks": max_tasks,
        "automation_fit_min": automation_fit_min,
        "target_path": target_path,
    }

    try:
        cfg = DriftConfig.load(repo_path)

        # Validate target_path existence
        warnings: list[str] = []
        if target_path and not (repo_path / target_path).exists():
            warnings.append(
                f"target_path '{target_path}' does not exist in repository"
            )

        analysis = analyze_repo(repo_path, config=cfg)
        tasks = analysis_to_agent_tasks(analysis)

        # Filter by target_path
        if target_path:
            normalized = Path(target_path).as_posix().strip("/")
            tasks = [
                t for t in tasks
                if t.file_path and (
                    Path(t.file_path).as_posix().strip("/") == normalized
                    or Path(t.file_path).as_posix().strip("/").startswith(normalized + "/")
                )
            ]

        # Filter by signal
        if signal:
            resolved = resolve_signal(signal)
            if resolved is None:
                result = _error_response(
                    "DRIFT-1003",
                    f"Unknown signal: '{signal}'",
                    invalid_fields=[{
                        "field": "signal", "value": signal,
                        "reason": "Not a valid signal ID",
                    }],
                    suggested_fix={
                        "action": "Use a valid signal abbreviation",
                        "valid_values": VALID_SIGNAL_IDS,
                        "example_call": {"tool": "drift_fix_plan", "params": {"signal": "PFS"}},
                    },
                )
                _emit_api_telemetry(
                    tool_name="api.fix_plan",
                    params=params,
                    status="ok",
                    elapsed_ms=elapsed_ms(),
                    result=result,
                    error=None,
                    repo_root=repo_path,
                )
                return result
            tasks = [t for t in tasks if t.signal_type == resolved]

        finding_id_diagnostic: str | None = None
        finding_id_message: str | None = None
        finding_id_suggested_fix: dict[str, Any] | None = None

        # Filter by finding_id
        if finding_id:
            id_matches = [t for t in tasks if t.id == finding_id]
            if id_matches:
                tasks = id_matches
            else:
                # Convenience: accept rule_id/signal-style IDs from scan output.
                resolved_finding = resolve_signal(finding_id)
                if resolved_finding is not None:
                    rule_matches = [t for t in tasks if t.signal_type == resolved_finding]
                    if rule_matches:
                        tasks = rule_matches
                        finding_id_diagnostic = "finding_id_interpreted_as_rule_id"
                        finding_id_message = (
                            f"'{finding_id}' was interpreted as rule_id/signal and matched "
                            f"{len(tasks)} task(s)."
                        )
                    else:
                        available_rule_ids = sorted({t.signal_type.value for t in tasks})
                        available_task_ids = [t.id for t in tasks]
                        tasks = []
                        finding_id_diagnostic = "finding_id_no_match"
                        finding_id_message = (
                            f"No findings matched finding_id '{finding_id}' in the current scope."
                        )
                        finding_id_suggested_fix = {
                            "action": (
                                "Use a task id from fix-plan output, or pass a valid "
                                "rule_id/signal "
                                "from scan output."
                            ),
                            "expected_formats": ["<signal>-<hash>", "<rule_id>", "<signal_abbrev>"],
                            "valid_task_ids_sample": available_task_ids[:10],
                            "valid_rule_ids": available_rule_ids,
                            "example_call": {
                                "tool": "drift_fix_plan",
                                "params": {"finding_id": "explainability_deficit", "max_tasks": 1},
                            },
                        }
                else:
                    available_rule_ids = sorted({t.signal_type.value for t in tasks})
                    available_task_ids = [t.id for t in tasks]
                    tasks = []
                    finding_id_diagnostic = "finding_id_no_match"
                    finding_id_message = (
                        f"No findings matched finding_id '{finding_id}' in the current scope."
                    )
                    finding_id_suggested_fix = {
                        "action": (
                            "Use a task id from fix-plan output, or pass a valid rule_id/signal "
                            "from scan output."
                        ),
                        "expected_formats": ["<signal>-<hash>", "<rule_id>", "<signal_abbrev>"],
                        "valid_task_ids_sample": available_task_ids[:10],
                        "valid_rule_ids": available_rule_ids,
                        "example_call": {
                            "tool": "drift_fix_plan",
                            "params": {"finding_id": "explainability_deficit", "max_tasks": 1},
                        },
                    }

        # Filter by automation fitness
        fit_levels = {"low": 0, "medium": 1, "high": 2}
        skipped_low = 0
        if automation_fit_min and automation_fit_min in fit_levels:
            min_level = fit_levels[automation_fit_min]
            filtered = []
            for t in tasks:
                if fit_levels.get(t.automation_fit, 0) >= min_level:
                    filtered.append(t)
                else:
                    skipped_low += 1
            tasks = filtered

        limited = tasks[:max_tasks]

        # Path diagnostic: explain empty results when target_path was used
        next_actions = ["drift_diff after applying fixes to verify improvement"]
        path_diagnostic = None
        if target_path and not tasks:
            normalized = Path(target_path).as_posix().strip("/")
            # Check if the path had any files in the analysis
            analyzed_paths = {
                f.file_path.as_posix().strip("/")
                for f in analysis.findings
                if f.file_path
            }
            if not any(
                p == normalized or p.startswith(normalized + "/")
                for p in analyzed_paths
            ):
                path_diagnostic = "no_matching_files"
                next_actions = [
                    f"Path '{target_path}' matched no analyzed files. "
                    f"Check spelling or use 'drift scan' to see available paths."
                ]
            else:
                path_diagnostic = "no_findings_in_path"
                next_actions = [
                    f"Path '{target_path}' contains analyzed files but has no actionable findings."
                ]

        result = _base_response(
            drift_score=round(analysis.drift_score, 4),
            tasks=[_task_to_api_dict(t) for t in limited],
            task_count=len(limited),
            total_available=len(tasks),
            skipped_low_automation=skipped_low,
            path_diagnostic=path_diagnostic,
            finding_id_diagnostic=finding_id_diagnostic,
            message=finding_id_message,
            suggested_fix=finding_id_suggested_fix,
            recommended_next_actions=next_actions,
            agent_instruction=(
                "After each file change, call drift_diff(uncommitted=True) "
                "before proceeding to the next file. Do not batch changes."
            ),
        )
        if warnings:
            result["warnings"] = warnings
        if finding_id and finding_id_message and not finding_id_suggested_fix:
            result.setdefault("warnings", []).append(finding_id_message)
        if finding_id and finding_id_suggested_fix:
            result.setdefault("invalid_fields", []).append(
                {
                    "field": "finding_id",
                    "value": finding_id,
                    "reason": "No task id or rule_id match in current scope",
                }
            )
        _emit_api_telemetry(
            tool_name="api.fix_plan",
            params=params,
            status="ok",
            elapsed_ms=elapsed_ms(),
            result=result,
            error=None,
            repo_root=repo_path,
        )
        return result
    except Exception as exc:
        _emit_api_telemetry(
            tool_name="api.fix_plan",
            params=params,
            status="error",
            elapsed_ms=elapsed_ms(),
            result=None,
            error=exc,
            repo_root=repo_path,
        )
        raise


def validate(
    path: str | Path = ".",
    *,
    config_file: str | None = None,
    baseline_file: str | None = None,
) -> dict[str, Any]:
    """Validate configuration and environment before analysis.

    Parameters
    ----------
    path:
        Repository root directory.
    config_file:
        Explicit config file path (auto-discovered if ``None``).
    baseline_file:
        Optional baseline file for progress comparison.  When provided,
        a quick scan is performed and the result is compared against the
        baseline to report score progress, resolved/new finding counts.
    """
    import subprocess

    from drift.telemetry import timed_call

    repo_path = Path(path).resolve()
    elapsed_ms = timed_call()
    params = {"path": str(path), "config_file": config_file, "baseline_file": baseline_file}

    try:
        # Check git availability
        git_available = False
        try:
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=repo_path,
                capture_output=True,
                check=True,
                timeout=5,
            )
            git_available = True
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            pass

        # Load and validate config
        warnings: list[str] = []
        config_source: str | None = None
        valid = True
        cfg = None

        try:
            from drift.config import DriftConfig

            cfg = DriftConfig.load(repo_path, Path(config_file) if config_file else None)
            cfg_path = DriftConfig._find_config_file(repo_path)
            config_source = str(cfg_path) if cfg_path else "defaults"

            # Weight checks
            weight_sum = sum(cfg.weights.as_dict().values())
            if weight_sum < 0.5 or weight_sum > 2.0:
                warnings.append(
                    f"Weight sum {weight_sum:.3f} outside [0.5, 2.0] "
                    "— auto-calibration will normalize"
                )
            for key, val in cfg.weights.as_dict().items():
                if val < 0:
                    warnings.append(f"Weight '{key}' is negative ({val})")
                    valid = False

            # Threshold checks
            thresh = cfg.thresholds.similarity_threshold
            if thresh < 0 or thresh > 1:
                warnings.append(f"similarity_threshold={thresh} outside [0, 1]")
                valid = False

        except Exception as exc:
            valid = False
            warnings.append(f"Config error: {exc}")

        # File discovery check
        files_discoverable = 0
        capabilities: list[str] = []
        if cfg is not None:
            try:
                from drift.ingestion.file_discovery import discover_files

                files = discover_files(repo_path, cfg.include, cfg.exclude)
                files_discoverable = len(files)
                langs = {f.language for f in files}
                if "python" in langs:
                    capabilities.append("python")
                if langs & {"typescript", "javascript"}:
                    capabilities.append("typescript")
            except Exception:
                pass

        # Embeddings check
        embeddings_available = False
        if cfg is not None:
            try:
                import importlib.util

                embeddings_available = (
                    cfg.embeddings_enabled
                    and importlib.util.find_spec("sentence_transformers") is not None
                )
            except Exception:
                pass

        result = _base_response(
            valid=valid,
            config_source=config_source,
            git_available=git_available,
            files_discoverable=files_discoverable,
            embeddings_available=embeddings_available,
            warnings=warnings,
            capabilities=capabilities,
        )

        # Optional baseline progress comparison
        if baseline_file and valid:
            try:
                from drift.baseline import load_baseline

                bl_fingerprints = load_baseline(Path(baseline_file))

                scan_result = scan(repo_path, max_findings=9999, response_detail="concise")
                score_after = scan_result.get("drift_score", 0.0)

                # Read baseline score from file
                import json as _json

                bl_data = _json.loads(Path(baseline_file).read_text(encoding="utf-8"))
                score_before = bl_data.get("drift_score", 0.0)

                # Count new vs resolved via fingerprints
                from drift.analyzer import analyze_repo
                from drift.baseline import baseline_diff as _bl_diff
                from drift.config import DriftConfig

                _cfg = DriftConfig.load(repo_path)
                _analysis = analyze_repo(repo_path, config=_cfg)
                new_findings, known_findings = _bl_diff(
                    _analysis.findings, bl_fingerprints
                )

                delta = round(score_after - score_before, 4)
                direction = "improved" if delta < -0.01 else (
                    "degraded" if delta > 0.01 else "stable"
                )
                result["progress"] = {
                    "baseline_file": str(baseline_file),
                    "score_before": round(score_before, 4),
                    "score_after": round(score_after, 4),
                    "delta": delta,
                    "direction": direction,
                    "resolved_count": len(known_findings),
                    "new_count": len(new_findings),
                    "progress_summary": (
                        f"{len(known_findings)} finding(s) resolved, "
                        f"{len(new_findings)} new, "
                        f"score {'improved' if delta < 0 else 'worsened'} by "
                        f"{abs(delta):.4f}"
                    ),
                }
            except Exception as exc_bl:
                result["progress"] = {
                    "error": f"Baseline comparison failed: {exc_bl}",
                }

        _emit_api_telemetry(
            tool_name="api.validate",
            params=params,
            status="ok",
            elapsed_ms=elapsed_ms(),
            result=result,
            error=None,
            repo_root=repo_path,
        )
        return result
    except Exception as exc:
        _emit_api_telemetry(
            tool_name="api.validate",
            params=params,
            status="error",
            elapsed_ms=elapsed_ms(),
            result=None,
            error=exc,
            repo_root=repo_path,
        )
        raise


# ---------------------------------------------------------------------------
# Nudge — incremental directional feedback (Phase 4, experimental)
# ---------------------------------------------------------------------------

# Delta threshold above which safe_to_commit is False
_NUDGE_SIGNIFICANT_DELTA = 0.05

# Legacy module-level baseline store — kept for backward compatibility
# but nudge() now uses BaselineManager.instance() instead.
_baseline_store: dict[
    str,
    tuple[
        BaselineSnapshot,
        list[Finding],
        dict[str, ParseResult],
    ],
] = {}


def _get_changed_files_from_git(
    repo_path: Path,
    *,
    uncommitted: bool = True,
) -> list[str]:
    """Return posix-relative paths of files changed in the working tree."""
    import subprocess

    args = ["git", "diff", "--name-only"]
    if uncommitted:
        args.append("HEAD")
    else:
        args.append("--cached")

    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=repo_path,
            check=True,
        )
        return [line for line in proc.stdout.strip().splitlines() if line]
    except Exception:
        return []


def nudge(
    path: str | Path = ".",
    *,
    changed_files: list[str] | None = None,
    uncommitted: bool = True,
) -> dict[str, Any]:
    """Incremental directional feedback after file changes.

    Runs file-local signals on changed files with exact confidence and
    carries forward cross-file / git-dependent findings from the baseline
    with estimated confidence.

    If no baseline exists for the repository, a full scan is performed
    first to establish one.

    Parameters
    ----------
    path:
        Repository root directory.
    changed_files:
        Explicit list of changed file paths (posix, relative to repo root).
        Auto-detected via ``git diff`` when ``None``.
    uncommitted:
        When auto-detecting, use uncommitted working-tree changes (default)
        vs. staged-only.

    Returns
    -------
    dict
        Nudge response with direction, delta, safe_to_commit, confidence map,
        new/resolved findings, and agent instruction.
    """
    import time as _time

    from drift.config import DriftConfig
    from drift.incremental import BaselineSnapshot, IncrementalSignalRunner
    from drift.ingestion.ast_parser import parse_file
    from drift.ingestion.file_discovery import discover_files

    start_ms = _time.monotonic()
    repo_path = Path(path).resolve()
    repo_key = repo_path.as_posix()

    params: dict[str, Any] = {
        "path": str(path),
        "changed_files": changed_files,
        "uncommitted": uncommitted,
    }
    parse_failed_files: list[dict[str, Any]] = []

    def record_parse_failure(
        *,
        file_path: str,
        stage: str,
        reason: str,
        errors: list[str] | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "file": file_path,
            "stage": stage,
            "reason": reason,
        }
        if errors:
            entry["errors"] = list(errors)
        parse_failed_files.append(entry)

    def elapsed_ms() -> int:
        return int((_time.monotonic() - start_ms) * 1_000)

    try:
        cfg = DriftConfig.load(repo_path)

        # -- Auto-detect changed files if not provided ----------------------
        if changed_files is None:
            changed_files = _get_changed_files_from_git(
                repo_path, uncommitted=uncommitted
            )
        changed_set = set(changed_files)

        # -- Ensure baseline exists via BaselineManager (Phase 5) -----------
        from drift.incremental import BaselineManager

        mgr = BaselineManager.instance()
        stored = mgr.get(repo_path)
        baseline_refresh_reason: str | None = None

        if stored is None:
            baseline_refresh_reason = (
                mgr.consume_refresh_reason(repo_path) or "baseline_missing"
            )
            # Run full scan to create baseline
            from drift.analyzer import analyze_repo

            analysis = analyze_repo(repo_path, config=cfg)
            all_files = discover_files(
                repo_path,
                include=cfg.include,
                exclude=cfg.exclude,
                max_files=cfg.thresholds.max_discovery_files,
            )
            # Build file_hashes + parse_results map
            from drift.cache import ParseCache

            file_hashes: dict[str, str] = {}
            parse_map: dict[str, ParseResult] = {}
            for finfo in all_files:
                full_path = repo_path / finfo.path
                try:
                    h = ParseCache.file_hash(full_path)
                    posix = finfo.path.as_posix()
                    file_hashes[posix] = h
                except OSError:
                    continue

            # Parse all files for baseline parse_results
            for finfo in all_files:
                try:
                    pr = parse_file(finfo.path, repo_path, finfo.language)
                    parse_map[finfo.path.as_posix()] = pr
                    if pr.parse_errors:
                        record_parse_failure(
                            file_path=finfo.path.as_posix(),
                            stage="baseline",
                            reason="parse_errors",
                            errors=pr.parse_errors,
                        )
                except Exception as exc:
                    record_parse_failure(
                        file_path=finfo.path.as_posix(),
                        stage="baseline",
                        reason="parse_exception",
                        errors=[str(exc)],
                    )
                    continue

            baseline = BaselineSnapshot(
                file_hashes=file_hashes,
                score=analysis.drift_score,
            )
            mgr.store(repo_path, baseline, list(analysis.findings), parse_map)
            stored = (baseline, list(analysis.findings), parse_map)
            # Sync legacy store for backward compat
            _baseline_store[repo_key] = stored

        baseline, baseline_findings, baseline_parse_map = stored

        # -- Parse only changed files ---------------------------------------
        current_parse: dict[str, ParseResult] = {}
        all_files_info = discover_files(
            repo_path,
            include=cfg.include,
            exclude=cfg.exclude,
            max_files=cfg.thresholds.max_discovery_files,
        )
        file_info_map = {f.path.as_posix(): f for f in all_files_info}
        for fp in changed_set:
            fi = file_info_map.get(fp)
            if fi is None:
                record_parse_failure(
                    file_path=fp,
                    stage="changed",
                    reason="file_not_discovered",
                    errors=["changed file is not part of discoverable source set"],
                )
                continue
            try:
                pr = parse_file(fi.path, repo_path, fi.language)
                current_parse[fp] = pr
                if pr.parse_errors:
                    record_parse_failure(
                        file_path=fp,
                        stage="changed",
                        reason="parse_errors",
                        errors=pr.parse_errors,
                    )
            except Exception as exc:
                record_parse_failure(
                    file_path=fp,
                    stage="changed",
                    reason="parse_exception",
                    errors=[str(exc)],
                )
                continue

        # De-duplicate for deterministic response contracts.
        parse_failed_files = sorted(
            {
                (
                    e["file"],
                    e["stage"],
                    e["reason"],
                    tuple(e.get("errors", [])),
                ): e
                for e in parse_failed_files
            }.values(),
            key=lambda e: (e["stage"], e["file"], e["reason"]),
        )
        parse_failure_count = len(parse_failed_files)

        # -- Run incremental analysis ---------------------------------------
        runner = IncrementalSignalRunner(
            baseline=baseline,
            config=cfg,
            baseline_findings=baseline_findings,
            baseline_parse_results=baseline_parse_map,
        )
        inc_result = runner.run(changed_set, current_parse)

        # -- safe_to_commit hardrule (Step 13) ------------------------------
        blocking_reasons: list[str] = []

        # Rule (a): new findings with critical/high severity
        for f in inc_result.new_findings:
            if f.severity.value in ("critical", "high"):
                blocking_reasons.append(
                    f"New {f.severity.value} finding: {f.title}"
                )
                break  # one reason suffices

        # Rule (b): significant degradation
        if inc_result.delta > _NUDGE_SIGNIFICANT_DELTA:
            blocking_reasons.append(
                f"Score degradation of {inc_result.delta:+.4f} exceeds threshold"
            )

        # Rule (c): expired baseline
        if not inc_result.baseline_valid:
            blocking_reasons.append("Baseline expired — full rescan recommended")

        # Rule (d): parse failures hide analyzable surface and therefore block commit safety.
        if parse_failure_count > 0:
            blocking_reasons.append(
                f"Parse failures in {parse_failure_count} file(s): "
                "affected files were skipped or only partially analyzable"
            )

        safe_to_commit = len(blocking_reasons) == 0

        # -- Magnitude label -----------------------------------------------
        abs_delta = abs(inc_result.delta)
        if abs_delta < 0.01:
            magnitude = "minor"
        elif abs_delta < 0.05:
            magnitude = "moderate"
        else:
            magnitude = "significant"

        # -- Nudge message --------------------------------------------------
        if inc_result.direction == "improving":
            nudge_msg = "Changes improve architectural coherence. Safe to proceed."
        elif inc_result.direction == "stable":
            nudge_msg = "No measurable drift impact. Continue."
        elif safe_to_commit:
            nudge_msg = (
                "Minor degradation detected but within acceptable bounds. "
                "Consider reviewing before committing."
            )
        else:
            nudge_msg = (
                "Significant drift detected. Review the blocking reasons "
                "before committing."
            )

        # -- Build response -------------------------------------------------
        result = _base_response(
            direction=inc_result.direction,
            delta=inc_result.delta,
            magnitude=magnitude,
            score=round(inc_result.score, 4),
            safe_to_commit=safe_to_commit,
            blocking_reasons=blocking_reasons,
            nudge=nudge_msg,
            new_findings=[_finding_concise(f) for f in inc_result.new_findings[:5]],
            resolved_findings=[
                _finding_concise(f) for f in inc_result.resolved_findings[:5]
            ],
            confidence=inc_result.confidence,
            expected_transient=False,  # MVP: always false (Step 14)
            baseline_age_seconds=round(
                _time.time() - baseline.created_at, 1
            ),
            baseline_valid=inc_result.baseline_valid,
            baseline_refresh_reason=baseline_refresh_reason,
            file_local_signals_run=inc_result.file_local_signals_run,
            cross_file_signals_estimated=inc_result.cross_file_signals_estimated,
            parse_failure_count=parse_failure_count,
            parse_failed_files=parse_failed_files,
            parse_failure_treatment={
                "affects_safe_to_commit": True,
                "policy": "blocking",
                "condition": "parse_failure_count > 0",
                "explanation": (
                    "Nudge marks safe_to_commit as false when parse failures are present "
                    "because impacted files were not fully analyzable."
                ),
            },
            changed_files=sorted(changed_set),
            agent_instruction=(
                "After each file change, call drift_nudge to check impact "
                "before proceeding. If safe_to_commit is false, address "
                "blocking_reasons first."
            ),
        )

        _emit_api_telemetry(
            tool_name="api.nudge",
            params=params,
            status="ok",
            elapsed_ms=elapsed_ms(),
            result=result,
            error=None,
            repo_root=repo_path,
        )
        return result

    except Exception as exc:
        _emit_api_telemetry(
            tool_name="api.nudge",
            params=params,
            status="error",
            elapsed_ms=elapsed_ms(),
            result=None,
            error=exc,
            repo_root=repo_path,
        )
        return _error_response("DRIFT-5001", str(exc), recoverable=True)


def invalidate_nudge_baseline(path: str | Path = ".") -> None:
    """Force a fresh baseline on the next nudge call for *path*."""
    from drift.incremental import BaselineManager

    repo_path = Path(path).resolve()
    repo_key = repo_path.as_posix()
    # Invalidate both BaselineManager and legacy store
    BaselineManager.instance().invalidate(repo_path)
    _baseline_store.pop(repo_key, None)


def to_json(result: dict[str, Any], *, indent: int = 2) -> str:
    """Serialize an API result dict to JSON string."""
    return json.dumps(result, indent=indent, default=str, sort_keys=True)


# ---------------------------------------------------------------------------
# Negative Context API
# ---------------------------------------------------------------------------


def negative_context(
    path: str | Path = ".",
    *,
    scope: str | None = None,
    target_file: str | None = None,
    max_items: int = 10,
    since_days: int = 90,
) -> dict[str, Any]:
    """Generate anti-pattern warnings from drift findings for agent consumption.

    Parameters
    ----------
    path:
        Repository root directory.
    scope:
        Filter by scope: ``"file"``, ``"module"``, or ``"repo"``.
    target_file:
        Restrict to items affecting a specific file (posix path).
    max_items:
        Maximum items to return (prioritized by severity).
    since_days:
        Days of git history to consider.

    Returns
    -------
    dict
        Negative context response with anti-pattern items and agent instruction.
    """
    from drift.analyzer import analyze_repo
    from drift.config import DriftConfig
    from drift.negative_context import (
        findings_to_negative_context,
        negative_context_to_dict,
    )
    from drift.telemetry import timed_call

    repo_path = Path(path).resolve()
    elapsed_ms = timed_call()
    params: dict[str, Any] = {
        "path": str(path),
        "scope": scope,
        "target_file": target_file,
        "max_items": max_items,
    }

    try:
        cfg = DriftConfig.load(repo_path)
        analysis = analyze_repo(
            repo_path, config=cfg, since_days=since_days,
        )

        items = findings_to_negative_context(
            analysis.findings,
            scope=scope,
            target_file=target_file,
            max_items=max_items,
        )

        result: dict[str, Any] = {
            "status": "ok",
            "drift_score": round(analysis.drift_score, 4),
            "items_returned": len(items),
            "items_total": len(analysis.findings),
            "scope_filter": scope,
            "target_file": target_file,
            "negative_context": [negative_context_to_dict(nc) for nc in items],
            "agent_instruction": (
                "These are known anti-patterns in this repository. "
                "Do NOT reproduce these patterns in new code. "
                "After generating code, call drift_nudge to verify "
                "you did not re-introduce any of these anti-patterns."
            ),
        }

        _emit_api_telemetry(
            tool_name="api.negative_context",
            params=params,
            status="ok",
            elapsed_ms=elapsed_ms(),
            result=result,
            error=None,
            repo_root=repo_path,
        )
        return result

    except Exception as exc:
        _emit_api_telemetry(
            tool_name="api.negative_context",
            params=params,
            status="error",
            elapsed_ms=elapsed_ms(),
            result=None,
            error=exc,
            repo_root=repo_path,
        )
        return _error_response("DRIFT-6001", str(exc), recoverable=True)

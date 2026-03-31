"""Programmatic API for drift analysis — agent-native, JSON-first.

This module provides the formalized public interface consumed by both the
MCP server and the CLI.  All functions return typed result dicts (not raw
``RepoAnalysis`` objects) so callers always receive a stable, serialisable
contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
    from drift.models import RepoAnalysis


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
    if strategy == "diverse":
        limited = _diverse_findings(analysis.findings, max_findings)
    else:
        ranked = sorted(
            analysis.findings, key=lambda f: f.impact, reverse=True,
        )
        limited = ranked[:max_findings]
    critical_count = sum(1 for f in analysis.findings if f.severity.value == "critical")
    high_count = sum(1 for f in analysis.findings if f.severity.value == "high")
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
        fix_first=_fix_first_concise(analysis, max_items=min(max_findings, 5)),
        finding_count=len(analysis.findings),
        critical_count=critical_count,
        high_count=high_count,
        findings_returned=len(limited),
        findings=findings_list,
        accept_change=not blocking_reasons,
        blocking_reasons=blocking_reasons,
        response_truncated=len(analysis.findings) > max_findings,
        recommended_next_actions=_scan_next_actions(analysis),
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


def _scan_next_actions(analysis: RepoAnalysis) -> list[str]:
    """Derive recommended tool calls from scan results."""
    actions: list[str] = []
    high_critical = sum(
        1 for f in analysis.findings
        if f.severity.value in ("critical", "high")
    )
    if analysis.findings:
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

        accept_change = not blocking_reasons
        in_scope_accept = not in_scope_blocking
        decision_reason_code, decision_reason = _diff_decision_reason(
            accept_change=accept_change,
            in_scope_accept=in_scope_accept,
            has_out_of_scope_noise=bool(out_of_scope_new),
        )

        _agent_hint = (
            "Score is improving. Safe to continue with next task."
            if status == "improved"
            else (
                "Score degraded. Call drift_fix_plan to address "
                "new findings before proceeding."
            )
            if status in ("degraded", "new_critical")
            else "No drift change detected. Safe to proceed."
        )
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
) -> list[str]:
    """Derive next actions from diff results."""
    actions: list[str] = []
    if status in ("degraded", "new_critical"):
        actions.append("drift_fix_plan for new findings")
    if any(f.severity.value in ("critical", "high") for f in new_findings):
        actions.append("drift_explain for high-severity signals")
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

        # Filter by finding_id
        if finding_id:
            tasks = [t for t in tasks if t.id == finding_id]

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
            recommended_next_actions=next_actions,
            agent_instruction=(
                "After each file change, call drift_diff(uncommitted=True) "
                "before proceeding to the next file. Do not batch changes."
            ),
        )
        if warnings:
            result["warnings"] = warnings
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


def to_json(result: dict[str, Any], *, indent: int = 2) -> str:
    """Serialize an API result dict to JSON string."""
    return json.dumps(result, indent=indent, default=str, sort_keys=True)

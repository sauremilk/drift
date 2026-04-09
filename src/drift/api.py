"""Programmatic API for drift analysis — agent-native, JSON-first.

This module provides the formalized public interface consumed by both the
MCP server and the CLI.  All functions return typed result dicts (not raw
``RepoAnalysis`` objects) so callers always receive a stable, serialisable
contract.
"""

from __future__ import annotations

import json
import logging as _logging
import threading
from collections import Counter
from collections.abc import Callable
from math import ceil
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from drift.api_helpers import (
    DONE_ACCEPT_CHANGE,
    DONE_DIFF_ACCEPT,
    DONE_NO_FINDINGS,
    DONE_NUDGE_SAFE,
    DONE_SAFE_TO_COMMIT,
    DONE_STAGED_EXISTS,
    DONE_TASK_AND_NUDGE,
    VALID_SIGNAL_IDS,
    _base_response,
    _error_response,
    _finding_concise,
    _finding_detailed,
    _fix_first_concise,
    _next_step_contract,
    _task_to_api_dict,
    _top_signals,
    _trend_dict,
    build_drift_score_scope,
    build_task_graph,
    build_workflow_plan,
    resolve_signal,
    severity_rank,
    shape_for_profile,
    signal_abbrev,
    signal_abbrev_map,
    signal_scope_label,
)
from drift.finding_context import is_non_operational_context, split_findings_by_context

if TYPE_CHECKING:
    from drift.analyzer import ProgressCallback
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
# Config sanity check (called after every DriftConfig.load)
# ---------------------------------------------------------------------------

_log = _logging.getLogger("drift")

_CONFIG_CACHE_LOCK = threading.RLock()
_CONFIG_CACHE: dict[tuple[str, str | None], tuple[int | None, Any]] = {}

_DIVERSE_MIN_TOP_IMPACT_SHARE = 0.4


def _config_mtime_ns(config_path: Path | None) -> int | None:
    """Return config mtime for cache invalidation, or None when unavailable."""
    if config_path is None:
        return None
    try:
        return config_path.stat().st_mtime_ns
    except OSError:
        return None


def _load_config_cached(
    repo_path: Path,
    config_file: Path | None = None,
) -> Any:
    """Load DriftConfig with a tiny in-process cache keyed by path+mtime."""
    from drift.config import DriftConfig

    resolved_repo = repo_path.resolve()
    resolved_config = (
        config_file.resolve()
        if config_file is not None
        else DriftConfig._find_config_file(resolved_repo)
    )
    key = (
        resolved_repo.as_posix(),
        resolved_config.as_posix() if resolved_config is not None else None,
    )
    mtime_ns = _config_mtime_ns(resolved_config)

    with _CONFIG_CACHE_LOCK:
        cached = _CONFIG_CACHE.get(key)
        if cached is not None and cached[0] == mtime_ns:
            return cached[1]

    cfg = DriftConfig.load(resolved_repo, resolved_config)

    with _CONFIG_CACHE_LOCK:
        _CONFIG_CACHE[key] = (mtime_ns, cfg)

    return cfg


def _diverse_top_impact_quota(max_findings: int) -> int:
    """Return guaranteed top-impact slots for the diverse strategy."""
    if max_findings <= 0:
        return 0
    return max(1, min(max_findings, int(ceil(max_findings * _DIVERSE_MIN_TOP_IMPACT_SHARE))))


def _warn_config_issues(cfg: Any) -> list[str]:
    """Return human-readable warnings for dangerous config values.

    Designed to be cheap enough to call on every API entry-point so that
    mis-configurations surface early instead of producing silently wrong
    results.
    """
    warnings: list[str] = []
    weights = getattr(cfg, "weights", None)
    if weights is not None and hasattr(weights, "as_dict"):
        for key, val in weights.as_dict().items():
            if val < 0:
                warnings.append(
                    f"Negative signal weight '{key}' = {val} — findings will be inverted"
                )
    thresholds = getattr(cfg, "thresholds", None)
    if thresholds is not None:
        thresh = getattr(thresholds, "similarity_threshold", None)
        if thresh is not None and (thresh < 0 or thresh > 1):
            warnings.append(f"similarity_threshold={thresh} outside valid range [0, 1]")
    if warnings:
        _log.warning("Config issues detected: %s", "; ".join(warnings))
    return warnings


# ---------------------------------------------------------------------------
# Core API functions
# ---------------------------------------------------------------------------


def scan(
    path: str | Path = ".",
    *,
    target_path: str | None = None,
    since_days: int = 90,
    signals: list[str] | None = None,
    exclude_signals: list[str] | None = None,
    max_findings: int = 10,
    max_per_signal: int | None = None,
    response_detail: str = "concise",
    strategy: str = "diverse",
    include_non_operational: bool = False,
    on_progress: Callable[[str, int, int], None] | None = None,
    response_profile: str | None = None,
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
    exclude_signals:
        Optional list of signal abbreviations to exclude.
    max_findings:
        Maximum number of findings in the response.
    max_per_signal:
        Optional cap for findings per signal in the returned list.
    response_detail:
        ``"concise"`` (token-sparing) or ``"detailed"`` (full fields).
    strategy:
        ``"diverse"`` (default) or ``"top-severity"`` (pure score sort).
    include_non_operational:
        Include non-operational contexts (fixture/generated/migration/docs)
        in prioritization queues when ``True``.
    on_progress:
        Optional callback ``(phase, current, total)`` for structured progress.
    """
    from drift.analyzer import analyze_repo
    from drift.config import apply_signal_filter, resolve_signal_names
    from drift.telemetry import timed_call

    repo_path = Path(path).resolve()
    elapsed_ms = timed_call()
    params = {
        "path": str(path),
        "target_path": target_path,
        "since_days": since_days,
        "signals": signals,
        "exclude_signals": exclude_signals,
        "max_findings": max_findings,
        "max_per_signal": max_per_signal,
        "response_detail": response_detail,
        "strategy": strategy,
        "include_non_operational": include_non_operational,
    }

    try:
        cfg = _load_config_cached(repo_path)
        cfg_warnings = _warn_config_issues(cfg)

        if max_per_signal is not None and max_per_signal < 1:
            raise ValueError("max_per_signal must be >= 1 when provided")

        # Validate target_path existence
        warnings: list[str] = cfg_warnings
        if target_path and not (repo_path / target_path).exists():
            warnings.append(
                f"target_path '{target_path}' does not exist in repository"
            )

        active_signals: set[str] | None = None
        select_csv = ",".join(signals) if signals else None
        ignore_csv = ",".join(exclude_signals) if exclude_signals else None
        if select_csv or ignore_csv:
            apply_signal_filter(cfg, select_csv, ignore_csv)
            if select_csv:
                active_signals = set(resolve_signal_names(select_csv))

        analysis = analyze_repo(
            repo_path,
            config=cfg,
            since_days=since_days,
            target_path=target_path,
            active_signals=active_signals,
            on_progress=on_progress,
        )
        result = _format_scan_response(
            analysis,
            config=cfg,
            max_findings=max_findings,
            max_per_signal=max_per_signal,
            detail=response_detail,
            strategy=strategy,
            signal_filter=set(s.upper() for s in signals) if signals else None,
            include_non_operational=include_non_operational,
            drift_score_scope=build_drift_score_scope(
                context="repo",
                path=target_path,
                signal_scope=signal_scope_label(selected=signals),
            ),
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
        return shape_for_profile(result, response_profile)
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
    1. Reserve a minimum share of highest-impact findings
       (preserves analyze/scan priority alignment).
    2. Add one top finding per yet-unseen signal with score >= 0.5.
    3. Fill remaining slots with highest-impact remaining findings.
    """
    if max_findings <= 0:
        return []

    by_score = sorted(
        findings,
        key=lambda f: (
            -f.impact,
            f.signal_type,
            f.file_path.as_posix() if f.file_path else "",
            f.start_line or 0,
        ),
    )

    if len(by_score) <= max_findings:
        return by_score

    # Phase 1: guaranteed top-impact floor.
    top_impact_quota = _diverse_top_impact_quota(max_findings)
    result: list = by_score[:top_impact_quota]
    selected_ids: set[int] = {id(f) for f in result}
    seen_signals: set[str] = {f.signal_type for f in result}

    # Phase 2: one representative per yet-unseen signal.
    for f in by_score:
        if len(result) >= max_findings:
            break
        if id(f) in selected_ids:
            continue
        sig = f.signal_type
        if sig not in seen_signals and f.score >= 0.5:
            seen_signals.add(sig)
            result.append(f)
            selected_ids.add(id(f))

    # Phase 3: fill remaining slots by impact ranking.
    if len(result) < max_findings:
        for f in by_score:
            if len(result) >= max_findings:
                break
            if id(f) in selected_ids:
                continue
            result.append(f)
            selected_ids.add(id(f))

    return result


def _apply_max_per_signal(
    initial: list,
    *,
    ranked_fallback: list,
    max_findings: int,
    max_per_signal: int,
) -> list:
    """Apply per-signal cap while preserving ordering and filling remaining slots."""
    counts: Counter[str] = Counter()
    selected: list = []
    selected_ids: set[int] = set()

    def _try_append(finding: Any) -> bool:
        signal = signal_abbrev(finding.signal_type)
        if counts[signal] >= max_per_signal:
            return False
        selected.append(finding)
        selected_ids.add(id(finding))
        counts[signal] += 1
        return True

    for finding in initial:
        if len(selected) >= max_findings:
            break
        _try_append(finding)

    if len(selected) >= max_findings:
        return selected

    for finding in ranked_fallback:
        if len(selected) >= max_findings:
            break
        if id(finding) in selected_ids:
            continue
        _try_append(finding)

    return selected


def _format_scan_response(
    analysis: RepoAnalysis,
    *,
    config: Any,
    max_findings: int = 10,
    max_per_signal: int | None = None,
    detail: str = "concise",
    strategy: str = "diverse",
    signal_filter: set[str] | None = None,
    include_non_operational: bool = False,
    drift_score_scope: str | None = None,
) -> dict[str, Any]:
    """Format a RepoAnalysis into the scan response schema."""
    if not hasattr(config, "finding_context"):
        from drift.config import DriftConfig

        config = DriftConfig()

    selected_findings = analysis.findings
    if signal_filter:
        selected_findings = [
            f for f in analysis.findings
            if signal_abbrev(f.signal_type) in signal_filter
        ]

    prioritized_for_fix_first, excluded_for_fix_first, context_counts = split_findings_by_context(
        selected_findings,
        config,
        include_non_operational=include_non_operational,
    )
    findings_for_prioritization = prioritized_for_fix_first

    ranked_selected = sorted(
        findings_for_prioritization,
        key=lambda f: (
            -f.impact,
            f.signal_type,
            f.file_path.as_posix() if f.file_path else "",
            f.start_line or 0,
        ),
    )

    if strategy == "diverse":
        limited = _diverse_findings(findings_for_prioritization, max_findings)
    else:
        limited = ranked_selected[:max_findings]

    if max_per_signal is not None:
        limited = _apply_max_per_signal(
            limited,
            ranked_fallback=ranked_selected,
            max_findings=max_findings,
            max_per_signal=max_per_signal,
        )

    selected_signal_counts: Counter[str] = Counter(
        signal_abbrev(f.signal_type) for f in findings_for_prioritization
    )
    included_signal_counts: Counter[str] = Counter(
        signal_abbrev(f.signal_type) for f in limited
    )
    omitted_signals: list[dict[str, Any]] = []
    for signal in sorted(selected_signal_counts.keys()):
        total = selected_signal_counts[signal]
        included = included_signal_counts.get(signal, 0)
        omitted = max(total - included, 0)
        if omitted:
            reason = "deprioritized_by_strategy"
            if max_per_signal is not None and included == max_per_signal:
                reason = "max_per_signal_cap"
            omitted_signals.append({
                "signal": signal,
                "total": total,
                "included": included,
                "omitted": omitted,
                "reason": reason,
            })

    omitted_signals.sort(key=lambda item: (-int(item["omitted"]), item["signal"]))

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

    top_sigs = _top_signals(analysis, signal_filter=signal_filter, config=config)

    # Deterministic tie-breaker: highest finding_count among max-score
    # signals, then alphabetical by signal abbreviation.
    # Only recommend signals with non-zero weight (scored signals).
    primary_signal: str | None = None
    if top_sigs:
        scored_sigs = [s for s in top_sigs if not s.get("report_only", False)]
        candidate_sigs = scored_sigs if scored_sigs else top_sigs
        max_score = candidate_sigs[0]["score"]
        tied = [s for s in candidate_sigs if s["score"] == max_score]
        tied.sort(key=lambda s: (-s["finding_count"], s["signal"]))
        primary_signal = tied[0]["signal"]

    result = _base_response(
        drift_score=round(analysis.drift_score, 3),
        drift_score_scope=drift_score_scope or build_drift_score_scope(context="repo"),
        signal_abbrev_map=signal_abbrev_map(),
        severity=analysis.severity.value,
        total_files=analysis.total_files,
        total_functions=analysis.total_functions,
        ai_ratio=round(analysis.ai_attributed_ratio, 3),
        trend=_trend_dict(analysis),
        primary_signal_for_next_step=primary_signal,
        # concise: top 3 signals only; detailed: all
        top_signals=top_sigs[:3] if detail == "concise" else top_sigs,
        finding_count=len(selected_findings),
        total_finding_count=len(analysis.findings),
        finding_count_by_signal=dict(
            Counter(signal_abbrev(f.signal_type) for f in analysis.findings)
        ),
        critical_count=critical_count,
        high_count=high_count,
        findings_returned=len(limited),
        findings=findings_list,
        accept_change=not blocking_reasons,
        blocking_reasons=blocking_reasons,
        response_truncated=len(selected_findings) > max_findings,
        finding_context={
            "counts": context_counts,
            "non_operational_contexts": sorted(
                set(config.finding_context.non_operational_contexts)
            ),
            "include_non_operational": include_non_operational,
            "excluded_from_prioritization": len(excluded_for_fix_first),
            "excluded_from_fix_first": len(excluded_for_fix_first),
        },
        cross_validation={
            "signal_fields": {
                "canonical_signal_type_field": "signal_type",
                "signal_id_field": "signal_id",
                "signal_abbrev_field": "signal_abbrev",
            },
            "severity_scale": {
                "ranking": {
                    level: severity_rank(level)
                    for level in ("critical", "high", "medium", "low", "info")
                },
                "higher_rank_means_higher_priority": True,
            },
            "numeric_score_range": {
                "min": 0.0,
                "max": 1.0,
                "fields": ["score", "impact", "score_contribution", "drift_score"],
            },
        },
    )

    selection_diagnostics: dict[str, Any] | None = None
    max_per_signal_limited = bool(
        max_per_signal is not None
        and len(findings_for_prioritization) > len(limited)
    )
    if len(findings_for_prioritization) > max_findings or max_per_signal_limited:
        selection_diagnostics = {
            "strategy": strategy,
            "max_findings": max_findings,
            "note": (
                "Some findings are not returned due to max_findings truncation "
                "and selection strategy."
            ),
        }
        if max_per_signal is not None:
            selection_diagnostics["max_per_signal"] = max_per_signal

        if omitted_signals:
            selection_diagnostics["signals_with_omitted_findings"] = omitted_signals
            suppressed_findings_by_signal = {
                str(item["signal"]): int(item["omitted"])
                for item in omitted_signals
            }
            selection_diagnostics["suppressed_findings_total"] = sum(
                suppressed_findings_by_signal.values()
            )
            selection_diagnostics["suppressed_findings_by_signal"] = (
                suppressed_findings_by_signal
            )

            if signal_filter and len(signal_filter) == 1:
                selected_signal = next(iter(signal_filter)).upper()
                suppressed_count = suppressed_findings_by_signal.get(selected_signal, 0)
                if suppressed_count > 0:
                    result[f"{selected_signal.lower()}_suppressed_findings"] = suppressed_count

        if strategy == "diverse" and max_findings > 0:
            top_window = ranked_selected[:max_findings]
            included_ids = {id(f) for f in limited}
            deprioritized_top_window = [f for f in top_window if id(f) not in included_ids]
            preserved = len(top_window) - len(deprioritized_top_window)
            top_window_size = len(top_window)
            preserved_share = (
                round(preserved / top_window_size, 3) if top_window_size else 1.0
            )
            top_window_diag: dict[str, Any] = {
                "window_size": top_window_size,
                "preserved": preserved,
                "preserved_share": preserved_share,
                "minimum_expected_share": _DIVERSE_MIN_TOP_IMPACT_SHARE,
            }
            if deprioritized_top_window:
                signal_counter = Counter(
                    signal_abbrev(f.signal_type) for f in deprioritized_top_window
                )
                top_window_diag["deprioritized_count"] = len(deprioritized_top_window)
                top_window_diag["deprioritized_signals"] = [
                    {"signal": signal, "count": count}
                    for signal, count in sorted(signal_counter.items())
                ]
            selection_diagnostics["top_impact_window"] = top_window_diag

    if selection_diagnostics:
        result["selection_diagnostics"] = selection_diagnostics

    # detailed mode adds fix_first, recommended_next_actions, agent_instruction
    if detail == "detailed":
        result["fix_first"] = _fix_first_concise(
            cast("RepoAnalysis", SimpleNamespace(findings=prioritized_for_fix_first)),
            max_items=min(max_findings, 5),
        )
        result["recommended_next_actions"] = _scan_next_actions(
            analysis,
            findings=selected_findings,
        )
        result["agent_instruction"] = _scan_agent_instruction(
            total_finding_count=len(analysis.findings),
        )
        result.update(_scan_next_step_contract(
            total_finding_count=len(analysis.findings),
            top_signal=result.get("primary_signal_for_next_step"),
        ))
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


# -- Batch-aware scan instruction (ADR-021) --------------------------------

_BATCH_SCAN_THRESHOLD = 20  # findings above this → batch-first guidance


def _scan_agent_instruction(*, total_finding_count: int) -> str:
    """Build context-dependent agent_instruction for scan responses.

    When the repository has many findings, the instruction steers the agent
    toward batch-first repair via fix_plan(max_tasks=20).  For small
    backlogs the traditional per-fix nudge loop is recommended.
    """
    if total_finding_count > _BATCH_SCAN_THRESHOLD:
        return (
            "Use drift_fix_plan(max_tasks=20) to get prioritised repair tasks. "
            "Start with batch_eligible tasks for maximum throughput — "
            "apply the same fix to ALL affected_files_for_pattern, then verify "
            "the batch with a single drift_diff(uncommitted=True). "
            "Use drift_nudge for quick directional checks between edits."
        )
    return (
        "Use drift_fix_plan to get prioritised repair tasks. "
        "After each fix, call drift_nudge for fast directional feedback. "
        "Use drift_diff before committing for full regression analysis."
    )


def _scan_next_step_contract(
    *,
    total_finding_count: int,
    top_signal: str | None,
) -> dict[str, Any]:
    """Build the next-step contract for scan responses (ADR-024)."""
    if total_finding_count == 0:
        return _next_step_contract(
            next_tool=None,
            done_when=DONE_NO_FINDINGS,
        )
    max_tasks = min(20, total_finding_count)
    return _next_step_contract(
        next_tool="drift_fix_plan",
        next_params={"max_tasks": max_tasks},
        done_when=DONE_ACCEPT_CHANGE,
        fallback_tool="drift_explain" if top_signal else None,
        fallback_params={"signal": top_signal} if top_signal else None,
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


def _repo_examples_for_signal(
    signal_abbr: str,
    repo_root: Path,
    *,
    max_examples: int = 5,
) -> list[dict[str, Any]]:
    """Return top findings for *signal_abbr* from this repo (best-effort).

    Runs a lightweight analysis.  If the analysis fails (e.g. no git repo),
    returns an empty list instead of raising.
    """
    try:
        from drift.analyzer import analyze_repo
        cfg = _load_config_cached(repo_root)
        analysis = analyze_repo(repo_root, config=cfg)
        sig_type = resolve_signal(signal_abbr)
        if sig_type is None:
            return []
        matches = [f for f in analysis.findings if f.signal_type == sig_type]
        matches.sort(key=lambda f: f.impact, reverse=True)
        examples: list[dict[str, Any]] = []
        for f in matches[:max_examples]:
            examples.append({
                "file": f.file_path.as_posix() if f.file_path else None,
                "line": f.start_line,
                "finding": f.title,
                "next_action": f.fix or f.description,
            })
        return examples
    except Exception:
        return []


def explain(
    topic: str,
    *,
    repo_path: str | Path | None = None,
    response_profile: str | None = None,
) -> dict[str, Any]:
    """Explain a signal, rule, or error code.

    Parameters
    ----------
    topic:
        A signal abbreviation (``"PFS"``), signal type name
        (``"pattern_fragmentation"``), or error code (``"DRIFT-1001"``).
    repo_path:
        Optional repository root.  When provided, a lightweight scan is
        performed and the top findings for the signal are included as
        ``repo_examples`` in the response.
    """
    import importlib

    explain_mod = importlib.import_module("drift.commands.explain")
    signal_info = cast(dict[str, dict[str, Any]], getattr(explain_mod, "_SIGNAL_INFO", {}))
    from drift.telemetry import timed_call

    elapsed_ms = timed_call()
    params = {"topic": topic, "repo_path": str(repo_path) if repo_path else None}

    try:
        # Try as signal abbreviation first
        upper = topic.upper()
        if upper in signal_info:
            info = signal_info[upper]
            result = _base_response(
                type="signal",
                signal=upper,
                name=info.get("name", upper),
                weight=float(info.get("weight", "0")),
                description=info.get("description", ""),
                detection_logic=info.get("detects", ""),
                typical_cause="Multiple AI sessions or copy-paste-modify patterns.",
                remediation_approach=info.get("fix_hint", ""),
                trigger_contract=info.get("trigger_contract"),
                related_signals=_related_signals(upper),
            )
            if repo_path:
                result["repo_examples"] = _repo_examples_for_signal(
                    upper, Path(repo_path).resolve(),
                )
            _emit_api_telemetry(
                tool_name="api.explain",
                params=params,
                status="ok",
                elapsed_ms=elapsed_ms(),
                result=result,
                error=None,
                repo_root=Path(repo_path).resolve() if repo_path else Path.cwd(),
            )
            return result

        # Try as SignalType value
        resolved = resolve_signal(topic)
        if resolved:
            abbr = signal_abbrev(resolved)
            if abbr in signal_info:
                result = explain(abbr, repo_path=repo_path)
                _emit_api_telemetry(
                    tool_name="api.explain",
                    params=params,
                    status="ok",
                    elapsed_ms=elapsed_ms(),
                    result=result,
                    error=None,
                    repo_root=Path(repo_path).resolve() if repo_path else Path.cwd(),
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
        from drift.errors import ERROR_REGISTRY, format_error_info_for_explain

        if topic.upper() in ERROR_REGISTRY:
            err = ERROR_REGISTRY[topic.upper()]
            summary, why, action = format_error_info_for_explain(topic.upper(), err)
            result = _base_response(
                type="error_code",
                error_code=err.code,
                category=err.category,
                summary=summary,
                why=why,
                action=action,
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
        return shape_for_profile(result, response_profile)
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


def _fix_plan_agent_instruction(tasks: list) -> str:
    """Build context-dependent agent_instruction for fix_plan responses."""
    batch_count = sum(1 for t in tasks if getattr(t, "metadata", {}).get("batch_eligible"))
    if batch_count > 0:
        return (
            "Tasks with batch_eligible=true share a fix pattern. "
            "Apply the fix to ALL affected_files_for_pattern, then verify "
            "with a single drift_diff(uncommitted=True). "
            "For non-batch tasks, use drift_nudge after each edit for fast "
            "directional feedback. Use drift_diff only for batch verification "
            "or before committing."
        )
    return (
        "After each fix, call drift_nudge for fast directional feedback. "
        "Use drift_diff for full regression analysis before committing. "
        "Do not batch changes across unrelated findings."
    )


def _fix_plan_next_step_contract(tasks: list) -> dict[str, Any]:
    """Build the next-step contract for fix_plan responses (ADR-024)."""
    batch_count = sum(1 for t in tasks if getattr(t, "metadata", {}).get("batch_eligible"))
    if batch_count > 0:
        return _next_step_contract(
            next_tool="drift_diff",
            next_params={"uncommitted": True},
            done_when=DONE_DIFF_ACCEPT,
            fallback_tool="drift_nudge",
        )
    return _next_step_contract(
        next_tool="drift_nudge",
        done_when=DONE_DIFF_ACCEPT,
        fallback_tool="drift_diff",
        fallback_params={"uncommitted": True},
    )


def fix_plan(
    path: str | Path = ".",
    *,
    finding_id: str | None = None,
    signal: str | None = None,
    max_tasks: int = 5,
    automation_fit_min: str | None = None,
    target_path: str | None = None,
    exclude_paths: list[str] | None = None,
    include_deferred: bool = False,
    include_non_operational: bool = False,
    on_progress: ProgressCallback | None = None,
    response_profile: str | None = None,
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
    exclude_paths:
        Exclude tasks whose file path is inside one of these subpaths.
    include_deferred:
        Include findings marked as ``deferred`` by config when ``True``.
    include_non_operational:
        Include non-operational contexts (fixture/generated/migration/docs)
        in prioritization when ``True``.
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
        "exclude_paths": exclude_paths,
        "include_deferred": include_deferred,
        "include_non_operational": include_non_operational,
    }

    _valid_automation_fit = {"low", "medium", "high"}

    try:
        if automation_fit_min is not None and automation_fit_min not in _valid_automation_fit:
            result = _error_response(
                "DRIFT-1003",
                f"Unknown automation_fit_min value: '{automation_fit_min}'",
                invalid_fields=[{
                    "field": "automation_fit_min",
                    "value": automation_fit_min,
                    "reason": "Must be one of: low, medium, high",
                }],
                suggested_fix={
                    "action": "Use a valid automation fitness level",
                    "valid_values": sorted(_valid_automation_fit),
                    "example_call": {
                        "tool": "drift_fix_plan",
                        "params": {"automation_fit_min": "medium"},
                    },
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

        cfg = _load_config_cached(repo_path)
        if not hasattr(cfg, "finding_context"):
            cfg = DriftConfig()
        cfg_warnings = _warn_config_issues(cfg)

        def _normalize_rel_path(raw: str | None) -> str:
            if not raw:
                return ""
            return Path(str(raw).replace("\\", "/")).as_posix().strip("/")

        def _in_scope(file_path: str | None, scope_path: str) -> bool:
            if not file_path:
                return False
            normalized_file = _normalize_rel_path(file_path)
            normalized_scope = _normalize_rel_path(scope_path)
            return (
                normalized_file == normalized_scope
                or normalized_file.startswith(normalized_scope + "/")
            )

        normalized_excludes = [
            _normalize_rel_path(p)
            for p in (exclude_paths or [])
            if _normalize_rel_path(p)
        ]

        # Validate target_path existence
        warnings: list[str] = cfg_warnings
        if target_path and not (repo_path / target_path).exists():
            warnings.append(
                f"target_path '{target_path}' does not exist in repository"
            )
        for excluded_path in normalized_excludes:
            if not (repo_path / excluded_path).exists():
                warnings.append(
                    f"exclude path '{excluded_path}' does not exist in repository"
                )

        analysis = analyze_repo(repo_path, config=cfg, on_progress=on_progress)
        tasks = analysis_to_agent_tasks(analysis)

        # Filter by target_path
        if target_path:
            tasks = [
                t for t in tasks
                if t.file_path and _in_scope(t.file_path, target_path)
            ]

        # Filter by exclude_paths
        if normalized_excludes:
            tasks = [
                t
                for t in tasks
                if not (
                    t.file_path
                    and any(_in_scope(t.file_path, excluded) for excluded in normalized_excludes)
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

        deferred_task_keys: set[tuple[str, str | None, str]] = set()
        for finding in analysis.findings:
            if not getattr(finding, "deferred", False):
                continue
            fp = finding.file_path.as_posix() if finding.file_path else None
            deferred_task_keys.add((finding.signal_type, fp, finding.title))

        excluded_deferred = 0
        if not include_deferred and deferred_task_keys:
            before = len(tasks)
            tasks = [
                t
                for t in tasks
                if (t.signal_type, t.file_path, t.title) not in deferred_task_keys
            ]
            excluded_deferred = before - len(tasks)
            if excluded_deferred > 0:
                warnings.append(
                    f"Excluded {excluded_deferred} deferred finding(s) from fix-plan scope"
                )

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
                        available_rule_ids = sorted({t.signal_type for t in tasks})
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
                    available_rule_ids = sorted({t.signal_type for t in tasks})
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

        context_counts: dict[str, int] = {}
        excluded_non_operational = 0
        if not include_non_operational:
            filtered_tasks = []
            for t in tasks:
                context = str(t.metadata.get("finding_context", "production"))
                context_counts[context] = context_counts.get(context, 0) + 1
                if is_non_operational_context(context, cfg):
                    excluded_non_operational += 1
                    continue
                filtered_tasks.append(t)
            tasks = filtered_tasks
        else:
            for t in tasks:
                context = str(t.metadata.get("finding_context", "production"))
                context_counts[context] = context_counts.get(context, 0) + 1

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

        # Compute remaining-by-signal for truncated tasks
        _remaining_tasks = tasks[len(limited):]
        _remaining_by_signal: dict[str, int] = {}
        for _rt in _remaining_tasks:
            _sig = signal_abbrev(_rt.signal_type)
            _remaining_by_signal[_sig] = _remaining_by_signal.get(_sig, 0) + 1

        # ADR-025 Phase A: build task dependency graph
        graph = build_task_graph(limited)

        # ADR-025 Phase C: build executable workflow plan
        workflow = build_workflow_plan(
            graph,
            repo_path=str(repo_path) if repo_path else ".",
        )

        result = _base_response(
            drift_score=round(analysis.drift_score, 3),
            drift_score_scope=build_drift_score_scope(
                context="fix-plan",
                path=target_path,
                signal_scope=signal_scope_label(selected=[signal] if signal else None),
            ),
            tasks=[_task_to_api_dict(t) for t in graph.tasks],
            task_count=len(limited),
            total_available=len(tasks),
            remaining_by_signal=_remaining_by_signal,
            skipped_low_automation=skipped_low,
            finding_context={
                "counts": dict(sorted(context_counts.items())),
                "non_operational_contexts": sorted(
                    set(cfg.finding_context.non_operational_contexts)
                ),
                "include_non_operational": include_non_operational,
                "excluded_from_fix_plan": excluded_non_operational,
            },
            path_diagnostic=path_diagnostic,
            finding_id_diagnostic=finding_id_diagnostic,
            message=finding_id_message,
            suggested_fix=finding_id_suggested_fix,
            recommended_next_actions=next_actions,
            agent_instruction=_fix_plan_agent_instruction(limited),
            task_graph=graph.to_api_dict(),
            workflow_plan=workflow.to_api_dict(),
        )
        result.update(_fix_plan_next_step_contract(limited))
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
        return shape_for_profile(result, response_profile)
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
    response_profile: str | None = None,
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
        # Path sandbox: config_file / baseline_file must be inside repo root
        for _field, _val in [("config_file", config_file), ("baseline_file", baseline_file)]:
            if _val is not None and not Path(_val).resolve().is_relative_to(repo_path):
                result = _error_response(
                    "DRIFT-1003",
                    f"{_field} must reside inside the repository root.",
                    invalid_fields=[{
                        "field": _field,
                        "value": _val,
                        "reason": "Path traversal outside repository root",
                    }],
                )
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

        # Check git availability
        git_available = False
        try:
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=repo_path,
                capture_output=True,
                check=True,
                timeout=5,
                stdin=subprocess.DEVNULL,
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

            cfg = _load_config_cached(repo_path, Path(config_file) if config_file else None)
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

                _cfg = _load_config_cached(repo_path)
                _analysis = analyze_repo(repo_path, config=_cfg)
                new_findings, known_findings = _bl_diff(
                    _analysis.findings, bl_fingerprints
                )

                delta = round(score_after - score_before, 4)
                direction = "improved" if delta < -0.01 else (
                    "degraded" if delta > 0.01 else "stable"
                )
                resolved_count = max(0, len(bl_fingerprints) - len(known_findings))
                known_count = len(known_findings)
                result["progress"] = {
                    "baseline_file": str(baseline_file),
                    "score_before": round(score_before, 4),
                    "score_after": round(score_after, 4),
                    "delta": delta,
                    "direction": direction,
                    "resolved_count": resolved_count,
                    "known_count": known_count,
                    "new_count": len(new_findings),
                    "progress_summary": (
                        f"{resolved_count} finding(s) resolved, "
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
        return shape_for_profile(result, response_profile)
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
) -> list[str] | None:
    """Return posix-relative paths of files changed in the working tree.

    Returns ``None`` when git is unavailable or fails, so callers can
    distinguish *no changes* (empty list) from *detection failed*.
    """
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
            stdin=subprocess.DEVNULL,
        )
        return [line for line in proc.stdout.strip().splitlines() if line]
    except Exception:
        _log.warning(
            "Could not detect changed files via git in %s; "
            "nudge will analyse all discovered files.",
            repo_path,
        )
        return None


def _nudge_next_step_contract(*, safe_to_commit: bool) -> dict[str, Any]:
    """Build the next-step contract for nudge responses (ADR-024)."""
    if safe_to_commit:
        return _next_step_contract(
            next_tool="drift_diff",
            next_params={"staged_only": True},
            done_when=DONE_DIFF_ACCEPT,
        )
    return _next_step_contract(
        next_tool="drift_fix_plan",
        done_when=DONE_SAFE_TO_COMMIT,
        fallback_tool="drift_scan",
        fallback_params={"response_detail": "concise"},
    )


def nudge(
    path: str | Path = ".",
    *,
    changed_files: list[str] | None = None,
    uncommitted: bool = True,
    signals: list[str] | None = None,
    exclude_signals: list[str] | None = None,
    response_profile: str | None = None,
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
    signals:
        Optional list of signal abbreviations to include in results.
        When set, only new/resolved findings matching these signals are returned.
    exclude_signals:
        Optional list of signal abbreviations to exclude from results.

    Returns
    -------
    dict
        Nudge response with direction, delta, safe_to_commit, confidence map,
        new/resolved findings, and agent instruction.
    """
    import time as _time

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
        cfg = _load_config_cached(repo_path)
        _warn_config_issues(cfg)

        # -- Auto-detect changed files if not provided ----------------------
        git_detection_failed = False
        if changed_files is None:
            detected = _get_changed_files_from_git(
                repo_path, uncommitted=uncommitted
            )
            if detected is None:
                git_detection_failed = True
                changed_files = []
            else:
                changed_files = detected
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

        # Rule (e): git detection failed — empty file-set is unreliable
        if git_detection_failed and not changed_set:
            blocking_reasons.append(
                "Git change detection failed; "
                "pass changed_files explicitly or check git availability"
            )

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
        # Apply signal filtering to new/resolved findings if requested
        _new = inc_result.new_findings
        _resolved = inc_result.resolved_findings
        if signals or exclude_signals:
            _include = {s.upper() for s in signals} if signals else None
            _exclude = {s.upper() for s in exclude_signals} if exclude_signals else set()
            def _sig_match(f: Finding) -> bool:
                abbr = signal_abbrev(f.signal_type)
                if _include is not None and abbr not in _include:
                    return False
                return abbr not in _exclude
            _new = [f for f in _new if _sig_match(f)]
            _resolved = [f for f in _resolved if _sig_match(f)]

        result = _base_response(
            direction=inc_result.direction,
            delta=inc_result.delta,
            magnitude=magnitude,
            score=round(inc_result.score, 4),
            safe_to_commit=safe_to_commit,
            blocking_reasons=blocking_reasons,
            nudge=nudge_msg,
            new_findings=[_finding_concise(f) for f in _new[:5]],
            resolved_findings=[
                _finding_concise(f) for f in _resolved[:5]
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
                "Use drift_nudge between edits for fast direction checks. "
                "If safe_to_commit is false, address blocking_reasons first. "
                "Call drift_diff after completing a batch for full verification."
            ),
        )
        result.update(_nudge_next_step_contract(safe_to_commit=safe_to_commit))

        _emit_api_telemetry(
            tool_name="api.nudge",
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
    disable_embeddings: bool = False,
    response_profile: str | None = None,
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
    disable_embeddings:
        Disable embedding-based analysis to keep response latency low.

    Returns
    -------
    dict
        Negative context response with anti-pattern items and agent instruction.
    """
    from drift.analyzer import analyze_repo
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
        "disable_embeddings": disable_embeddings,
    }

    try:
        cfg = _load_config_cached(repo_path)
        _warn_config_issues(cfg)
        if disable_embeddings:
            cfg.embeddings_enabled = False
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
            "drift_score": round(analysis.drift_score, 3),
            "drift_score_scope": build_drift_score_scope(
                context=f"negative-context:{scope or 'repo'}",
                path=target_file,
            ),
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
            **_next_step_contract(
                next_tool="drift_nudge",
                done_when=DONE_NUDGE_SAFE,
                fallback_tool="drift_scan",
                fallback_params={"response_detail": "concise"},
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
        return shape_for_profile(result, response_profile)

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


# ---------------------------------------------------------------------------
# brief — pre-task structural briefing
# ---------------------------------------------------------------------------

# Pre-task relevance factors (from guardrails module)
_BRIEF_RELEVANCE: dict[str, float] = {
    "AVS": 1.0, "PFS": 1.0, "MDS": 1.0,
    "CCC": 0.7, "CIR": 0.7, "FOE": 0.7,
    "BEM": 0.4, "ECM": 0.4, "EDS": 0.4, "COD": 0.4,
    "TPD": 0.1, "GCD": 0.1, "NBV": 0.1, "DIA": 0.1,
}


def _compute_scope_risk(
    findings: list[Finding],
    config: Any,
) -> float:
    """Compute a weighted scope risk score from scoped findings.

    Formula (spec §3.3):
        scope_risk = Σ(weight × score × relevance) / Σ(weight × relevance)
    """
    numerator = 0.0
    denominator = 0.0

    for f in findings:
        abbrev = signal_abbrev(f.signal_type)
        has_weights = hasattr(config, "weights")
        weight = float(getattr(config.weights, f.signal_type, 1.0)) if has_weights else 1.0
        relevance = _BRIEF_RELEVANCE.get(abbrev, 0.0)
        if relevance == 0.0:
            continue
        numerator += weight * f.score * relevance
        denominator += weight * relevance

    if denominator == 0.0:
        return 0.0
    return min(numerator / denominator, 1.0)


def _risk_level(score: float, findings: list[Finding]) -> str:
    """Map scope risk score to risk level string.

    BLOCK is also triggered by any CRITICAL AVS finding in scope.
    """
    from drift.models import Severity as _Sev
    from drift.models import SignalType as _SigT  # noqa: N814

    # Check for CRITICAL AVS
    for f in findings:
        if (
            f.signal_type == _SigT.ARCHITECTURE_VIOLATION
            and f.severity == _Sev.CRITICAL
        ):
            return "BLOCK"

    if score >= 0.75:
        return "BLOCK"
    if score >= 0.50:
        return "HIGH"
    if score >= 0.25:
        return "MEDIUM"
    return "LOW"


def _risk_reason(findings: list[Finding], level: str) -> str:
    """Generate a human-readable reason for the risk level."""
    if not findings:
        return "No structural findings in scope"

    from collections import Counter

    signal_counts: Counter[str] = Counter(
        signal_abbrev(f.signal_type) for f in findings
    )
    top_signal, top_count = signal_counts.most_common(1)[0]
    plural = "s" if top_count != 1 else ""
    return f"{top_count} {top_signal} finding{plural} in scope (risk: {level})"


# Pre-task-relevant signals: only run signals that are actionable before
# writing code.  brief() uses this set by default to skip irrelevant
# signals and speed up analysis.
_PRE_TASK_SIGNALS: set[str] = {
    "architecture_violation",       # AVS — critical
    "pattern_fragmentation",        # PFS — critical
    "mutant_duplicate",             # MDS — critical
    "co_change_coupling",           # CCC — high
    "circular_import",              # CIR — high
    "fan_out_explosion",            # FOE — high
    "broad_exception_monoculture",  # BEM — medium
    "exception_contract_drift",     # ECM — medium
    "explainability_deficit",       # EDS — medium
    "cohesion_deficit",             # COD — medium
}


def _brief_next_step_contract(risk_level: str) -> dict[str, Any]:
    """Build the next-step contract for brief responses (ADR-024)."""
    if risk_level == "high":
        return _next_step_contract(
            next_tool="drift_scan",
            done_when=DONE_TASK_AND_NUDGE,
            fallback_tool="drift_negative_context",
        )
    return _next_step_contract(
        next_tool="drift_negative_context",
        done_when=DONE_TASK_AND_NUDGE,
        fallback_tool="drift_nudge",
    )


def brief(
    path: str | Path = ".",
    *,
    task: str,
    scope_override: str | None = None,
    signals: list[str] | None = None,
    max_guardrails: int = 10,
    include_non_operational: bool = False,
    on_progress: ProgressCallback | None = None,
    response_profile: str | None = None,
) -> dict[str, Any]:
    """Generate a pre-task structural briefing for agent delegation.

    Analyses the scope affected by a natural-language task description and
    produces guardrails (prompt constraints) that reduce architectural
    erosion risk during AI-assisted code generation.

    Parameters
    ----------
    path:
        Repository root directory.
    task:
        Natural-language task description
        (e.g. ``"add payment integration to checkout module"``).
    scope_override:
        Manual scope override (path or glob).  Skips heuristic resolution.
    signals:
        Optional list of signal abbreviations to evaluate.
    max_guardrails:
        Maximum number of guardrails in the response.
    include_non_operational:
        Include fixture/generated/migration/docs findings.
    """
    from drift.analyzer import analyze_repo
    from drift.config import apply_signal_filter, resolve_signal_names
    from drift.guardrails import generate_guardrails, guardrails_to_prompt_block
    from drift.models import Severity
    from drift.scope_resolver import expand_scope_imports, resolve_scope
    from drift.telemetry import timed_call

    repo_path = Path(path).resolve()
    elapsed_ms = timed_call()
    params = {
        "path": str(path),
        "task": task,
        "scope_override": scope_override,
        "signals": signals,
        "max_guardrails": max_guardrails,
        "include_non_operational": include_non_operational,
    }

    try:
        cfg = _load_config_cached(repo_path)
        _warn_config_issues(cfg)

        # --- Scope resolution ------------------------------------------------
        layer_names = None
        if hasattr(cfg, "policy") and hasattr(cfg.policy, "layer_boundaries"):
            layer_names = [lb.name for lb in cfg.policy.layer_boundaries]

        # Keyword aliases from drift.yaml brief.scope_aliases
        scope_aliases: dict[str, str] | None = None
        if hasattr(cfg, "brief") and cfg.brief.scope_aliases:
            scope_aliases = cfg.brief.scope_aliases

        scope = resolve_scope(
            task,
            repo_path,
            scope_override=scope_override,
            layer_names=layer_names,
            scope_aliases=scope_aliases,
        )

        # 1-hop import expansion — include direct dependencies
        expanded_paths = expand_scope_imports(scope, repo_path)

        # --- Signal filter ---------------------------------------------------
        active_signals: set[str] | None = None
        if signals:
            select_csv = ",".join(signals)
            apply_signal_filter(cfg, select_csv, None)
            active_signals = set(resolve_signal_names(select_csv))
        else:
            # Apply pre-task signal filter for performance
            pre_csv = ",".join(_PRE_TASK_SIGNALS)
            apply_signal_filter(cfg, pre_csv, None)
            active_signals = _PRE_TASK_SIGNALS

        # --- Run analysis (full repo for signal context) --------------------
        # Run analysis on the full repository to ensure signals like PFS get
        # complete context, then filter findings to the resolved scope (#157).
        analysis = analyze_repo(
            repo_path,
            config=cfg,
            since_days=90,
            on_progress=on_progress,
            active_signals=active_signals,
        )

        # Scope filtering: always filter findings to the resolved paths
        # (including 1-hop dependency paths).
        all_scope_paths = scope.paths + expanded_paths
        scoped_findings = analysis.findings
        if all_scope_paths:
            def _in_scope(f: Finding) -> bool:
                if not f.file_path:
                    return True
                fp = f.file_path.as_posix().strip("/")
                return any(
                    fp == p or fp.startswith(p + "/") or p.startswith(fp + "/")
                    for p in all_scope_paths
                )
            scoped_findings = [f for f in analysis.findings if _in_scope(f)]

        # Filter non-operational if needed
        if not include_non_operational:
            op, _non_op, _ctx_counts = split_findings_by_context(
                scoped_findings, cfg, include_non_operational=False,
            )
            scoped_findings = op

        # Populate scope stats
        scope.file_count = analysis.total_files
        scope.function_count = analysis.total_functions

        # --- Risk calculation ------------------------------------------------
        scope_risk = _compute_scope_risk(scoped_findings, cfg)
        level = _risk_level(scope_risk, scoped_findings)
        reason = _risk_reason(scoped_findings, level)

        # Find blocking signals
        blocking_signals = sorted({
            signal_abbrev(f.signal_type)
            for f in scoped_findings
            if f.severity in (Severity.CRITICAL, Severity.HIGH)
        })

        # --- Guardrails ------------------------------------------------------
        guardrails = generate_guardrails(
            scoped_findings,
            max_guardrails=max_guardrails,
        )
        prompt_block = guardrails_to_prompt_block(guardrails)

        # --- Top signals (scoped) --------------------------------------------
        top_sigs = _top_signals(
            analysis,
            signal_filter=set(s.upper() for s in signals) if signals else None,
            config=cfg,
        )

        # --- Build response --------------------------------------------------
        result = _base_response(
            type="brief",
            task=task,
            scope={
                "resolved_paths": scope.paths,
                "expanded_dependency_paths": expanded_paths,
                "resolution_method": scope.method,
                "file_count": scope.file_count,
                "function_count": scope.function_count,
                "confidence": round(scope.confidence, 2),
                "matched_tokens": scope.matched_tokens,
            },
            risk={
                "level": level,
                "score": round(scope_risk, 3),
                "reason": reason,
                "blocking_signals": blocking_signals,
            },
            landscape={
                "drift_score": round(analysis.drift_score, 3),
                "drift_score_scope": build_drift_score_scope(
                    context="brief",
                    path=scope.paths[0] if scope.paths else None,
                    signal_scope=(
                        signal_scope_label(selected=signals)
                        if signals
                        else "pre-task-default"
                    ),
                ),
                "severity": analysis.severity.value,
                "top_signals": top_sigs,
                "finding_count": len(scoped_findings),
            },
            guardrails=[g.to_dict() for g in guardrails],
            guardrails_prompt_block=prompt_block,
            recommended_next=["drift diff --uncommitted", "drift nudge"],
            meta={
                "analysis_duration_ms": round(elapsed_ms() * 1.0, 0),
                "signals_evaluated": len(top_sigs),
                "repo_path": str(repo_path),
            },
        )
        result.update(_brief_next_step_contract(level))

        _emit_api_telemetry(
            tool_name="api.brief",
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
            tool_name="api.brief",
            params=params,
            status="error",
            elapsed_ms=elapsed_ms(),
            result=None,
            error=exc,
            repo_root=repo_path,
        )
        raise

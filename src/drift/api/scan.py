"""Scan endpoint — full drift analysis returning a structured result dict."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from math import ceil
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

from drift.api._config import (
    _emit_api_telemetry,
    _load_config_cached,
    _warn_config_issues,
)
from drift.api_helpers import (
    DONE_ACCEPT_CHANGE,
    DONE_NO_FINDINGS,
    _base_response,
    _finding_concise,
    _finding_detailed,
    _fix_first_concise,
    _next_step_contract,
    _top_signals,
    _trend_dict,
    build_drift_score_scope,
    severity_rank,
    shape_for_profile,
    signal_abbrev,
    signal_abbrev_map,
    signal_scope_label,
)
from drift.finding_context import split_findings_by_context

if TYPE_CHECKING:
    from drift.models import RepoAnalysis

# ---------------------------------------------------------------------------
# Diverse-strategy helpers
# ---------------------------------------------------------------------------

_DIVERSE_MIN_TOP_IMPACT_SHARE = 0.4


def _diverse_top_impact_quota(max_findings: int) -> int:
    """Return guaranteed top-impact slots for the diverse strategy."""
    if max_findings <= 0:
        return 0
    return max(1, min(max_findings, int(ceil(max_findings * _DIVERSE_MIN_TOP_IMPACT_SHARE))))


# -- Batch-aware scan instruction (ADR-021) --------------------------------

_BATCH_SCAN_THRESHOLD = 20  # findings above this → batch-first guidance


# ---------------------------------------------------------------------------
# Core scan API
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

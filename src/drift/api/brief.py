"""Brief endpoint — pre-task structural briefing for agent delegation."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from drift.api._config import (
    _emit_api_telemetry,
    _load_config_cached,
    _warn_config_issues,
)
from drift.api_helpers import (
    DONE_TASK_AND_NUDGE,
    _base_response,
    _next_step_contract,
    _top_signals,
    build_drift_score_scope,
    shape_for_profile,
    signal_abbrev,
    signal_scope_label,
)
from drift.finding_context import split_findings_by_context

if TYPE_CHECKING:
    from drift.analyzer import ProgressCallback
    from drift.models import Finding

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

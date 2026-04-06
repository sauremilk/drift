"""Shared helper utilities for the public drift API module.

This module contains reusable signal mapping and response-shaping helpers that
are consumed by ``drift.api``. Keeping helpers here reduces api.py size while
preserving the existing public API surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from drift.config import DriftConfig
from drift.finding_context import classify_finding_context
from drift.models import SignalType

if TYPE_CHECKING:
    from drift.models import RepoAnalysis


SCHEMA_VERSION = "2.0"


_SEVERITY_RANK: dict[str, int] = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "info": 1,
}


_ABBREV_TO_SIGNAL: dict[str, SignalType] = {
    "PFS": SignalType.PATTERN_FRAGMENTATION,
    "AVS": SignalType.ARCHITECTURE_VIOLATION,
    "MDS": SignalType.MUTANT_DUPLICATE,
    "TVS": SignalType.TEMPORAL_VOLATILITY,
    "EDS": SignalType.EXPLAINABILITY_DEFICIT,
    "SMS": SignalType.SYSTEM_MISALIGNMENT,
    "DIA": SignalType.DOC_IMPL_DRIFT,
    "BEM": SignalType.BROAD_EXCEPTION_MONOCULTURE,
    "TPD": SignalType.TEST_POLARITY_DEFICIT,
    "GCD": SignalType.GUARD_CLAUSE_DEFICIT,
    "NBV": SignalType.NAMING_CONTRACT_VIOLATION,
    "BAT": SignalType.BYPASS_ACCUMULATION,
    "ECM": SignalType.EXCEPTION_CONTRACT_DRIFT,
    "COD": SignalType.COHESION_DEFICIT,
    "CCC": SignalType.CO_CHANGE_COUPLING,
    "TSA": SignalType.TS_ARCHITECTURE,
    "CXS": SignalType.COGNITIVE_COMPLEXITY,
    "FOE": SignalType.FAN_OUT_EXPLOSION,
    "CIR": SignalType.CIRCULAR_IMPORT,
    "DCA": SignalType.DEAD_CODE_ACCUMULATION,
    "MAZ": SignalType.MISSING_AUTHORIZATION,
    "ISD": SignalType.INSECURE_DEFAULT,
    "HSC": SignalType.HARDCODED_SECRET,
}

_SIGNAL_TO_ABBREV: dict[str, str] = {v.value: k for k, v in _ABBREV_TO_SIGNAL.items()}

VALID_SIGNAL_IDS = sorted(_ABBREV_TO_SIGNAL.keys())


def signal_abbrev_map() -> dict[str, str]:
    """Return stable abbreviation -> canonical signal_type mapping."""
    return {
        abbrev: signal_type.value
        for abbrev, signal_type in sorted(_ABBREV_TO_SIGNAL.items())
    }


def resolve_signal(name: str) -> SignalType | None:
    """Resolve a signal abbreviation or full name to ``SignalType``."""
    upper = name.upper()
    if upper in _ABBREV_TO_SIGNAL:
        return _ABBREV_TO_SIGNAL[upper]
    try:
        return SignalType(name)
    except ValueError:
        return None


def signal_abbrev(signal_type: SignalType) -> str:
    """Return the short abbreviation for a signal type."""
    return _SIGNAL_TO_ABBREV.get(signal_type.value, signal_type.value[:3].upper())


def signal_scope_label(
    *,
    selected: list[str] | None = None,
    ignored: list[str] | None = None,
) -> str:
    """Build a compact label describing which signals contributed to a score."""
    if selected:
        normalized = sorted({item.strip().upper() for item in selected if item.strip()})
        if normalized:
            return "+".join(normalized)
    if ignored:
        normalized = sorted({item.strip().upper() for item in ignored if item.strip()})
        if normalized:
            return f"all-minus:{'+'.join(normalized)}"
    return "all"


def build_drift_score_scope(
    *,
    context: str,
    path: str | None = None,
    signal_scope: str = "all",
    baseline_filtered: bool = False,
) -> str:
    """Return a stable scope descriptor for drift_score values."""
    normalized_path = (path or "all").strip("/") or "all"
    parts = [
        f"context:{context}",
        f"signals:{signal_scope}",
        f"path:{normalized_path}",
    ]
    if baseline_filtered:
        parts.append("baseline:filtered")
    return ",".join(parts)


def _base_response(**extra: Any) -> dict[str, Any]:
    """Build the common response envelope."""
    return {"schema_version": SCHEMA_VERSION, **extra}


def _finding_fingerprint_value(f: Any) -> str:
    """Return deterministic fingerprint for finding-like objects used by API responses."""
    from drift.baseline import finding_fingerprint

    return finding_fingerprint(f)


def severity_rank(value: str) -> int:
    """Return numeric severity rank for cross-command comparisons."""
    return _SEVERITY_RANK.get(value, 0)


def _finding_concise(f: Any) -> dict[str, Any]:
    """Minimal finding dict for concise responses."""
    from drift.output.json_output import _next_step_for_finding

    signal = signal_abbrev(f.signal_type)
    severity = f.severity.value

    return {
        "signal": signal,
        "signal_abbrev": signal,
        "signal_id": signal,
        "signal_type": f.signal_type.value,
        "rule_id": f.rule_id,
        "severity": severity,
        "severity_rank": severity_rank(severity),
        "title": f.title,
        "file": f.file_path.as_posix() if f.file_path else None,
        "line": f.start_line,
        "finding_context": classify_finding_context(f, DriftConfig()),
        "fingerprint": _finding_fingerprint_value(f),
        "next_step": _next_step_for_finding(f),
    }


def _finding_detailed(f: Any, *, rank: int | None = None) -> dict[str, Any]:
    """Full finding dict for detailed responses."""
    from drift.output.json_output import (
        _expected_benefit_for_finding,
        _next_step_for_finding,
        _priority_class,
    )
    from drift.recommendations import generate_recommendation

    rec = generate_recommendation(f)
    signal = signal_abbrev(f.signal_type)
    severity = f.severity.value
    return {
        "signal": signal,
        "signal_abbrev": signal,
        "signal_id": signal,
        "signal_type": f.signal_type.value,
        "rule_id": f.rule_id,
        "severity": severity,
        "severity_rank": severity_rank(severity),
        "score": f.score,
        "impact": f.impact,
        "score_contribution": f.score_contribution,
        "priority_class": _priority_class(f),
        "title": f.title,
        "description": f.description,
        "fix": f.fix,
        "file": f.file_path.as_posix() if f.file_path else None,
        "start_line": f.start_line,
        "end_line": f.end_line,
        "finding_context": classify_finding_context(f, DriftConfig()),
        "symbol": f.symbol,
        "related_files": [rf.as_posix() for rf in f.related_files],
        "fingerprint": _finding_fingerprint_value(f),
        "next_step": _next_step_for_finding(f),
        "expected_benefit": _expected_benefit_for_finding(f),
        "remediation": {
            "title": rec.title,
            "description": rec.description,
            "effort": rec.effort,
            "impact": rec.impact,
        }
        if rec
        else None,
    }


def _trend_dict(analysis: RepoAnalysis) -> dict[str, Any] | None:
    if not analysis.trend:
        return None
    return {
        "direction": analysis.trend.direction,
        "delta": analysis.trend.delta,
        "previous_score": analysis.trend.previous_score,
    }


def _signal_weight(abbrev: str, config: Any) -> float:
    """Return the scoring weight for a signal abbreviation."""
    sig_type = _ABBREV_TO_SIGNAL.get(abbrev)
    if sig_type is None or not hasattr(config, "weights"):
        return 1.0
    return float(getattr(config.weights, sig_type.value, 1.0))


def _top_signals(
    analysis: RepoAnalysis,
    *,
    signal_filter: set[str] | None = None,
    config: Any = None,
) -> list[dict[str, Any]]:
    """Aggregate signal scores and finding counts."""
    from collections import Counter

    counts: Counter[str] = Counter()
    score_sums: dict[str, float] = {}
    for f in analysis.findings:
        abbr = signal_abbrev(f.signal_type)
        if signal_filter and abbr not in signal_filter:
            continue
        counts[abbr] += 1
        score_sums[abbr] = max(score_sums.get(abbr, 0.0), f.score)

    result = []
    for sig in counts:
        w = _signal_weight(sig, config) if config else 1.0
        result.append({
            "signal": sig,
            "score": round(score_sums[sig], 3),
            "finding_count": counts[sig],
            "weight": round(w, 4),
            "report_only": w == 0.0,
        })

    return sorted(
        result,
        key=lambda x: (-x["score"], -x["finding_count"], x["signal"]),
    )


def _fix_first_concise(analysis: RepoAnalysis, max_items: int = 5) -> list[dict[str, Any]]:
    """Build compact fix_first list (deduplicated)."""
    from drift.output.json_output import (
        _SEVERITY_RANK,
        _dedupe_findings,
        _expected_benefit_for_finding,
        _next_step_for_finding,
        _priority_class,
        _priority_rank,
    )

    deduped, _counts = _dedupe_findings(analysis.findings)

    prioritized = sorted(
        deduped,
        key=lambda f: (
            _priority_rank(_priority_class(f)),
            _SEVERITY_RANK[f.severity],
            -float(f.impact),
        ),
    )

    seen_file_signal: set[tuple[str, str]] = set()
    unique: list = []
    for f in prioritized:
        fp = f.file_path.as_posix() if f.file_path else ""
        key = (fp, f.signal_type.value)
        if key not in seen_file_signal:
            seen_file_signal.add(key)
            unique.append(f)

    items: list[dict[str, Any]] = []
    for idx, f in enumerate(unique[:max_items], start=1):
        signal = signal_abbrev(f.signal_type)
        severity = f.severity.value
        items.append(
            {
                "rank": idx,
                "signal": signal,
                "signal_abbrev": signal,
                "signal_id": signal,
                "signal_type": f.signal_type.value,
                "severity": severity,
                "severity_rank": severity_rank(severity),
                "title": f.title,
                "file": f.file_path.as_posix() if f.file_path else None,
                "line": f.start_line,
                "finding_context": classify_finding_context(f, DriftConfig()),
                "fingerprint": _finding_fingerprint_value(f),
                "next_step": _next_step_for_finding(f),
                "expected_benefit": _expected_benefit_for_finding(f),
            }
        )
    return items


def _task_to_api_dict(t: Any) -> dict[str, Any]:
    """Convert an AgentTask to the API dict format."""
    return {
        "id": t.id,
        "priority": t.priority,
        "signal": signal_abbrev(t.signal_type),
        "signal_abbrev": signal_abbrev(t.signal_type),
        "severity": t.severity.value,
        "title": t.title,
        "action": t.action,
        "finding_context": t.metadata.get("finding_context", "production"),
        "file": t.file_path,
        "start_line": t.start_line,
        "symbol": t.symbol,
        "related_files": t.related_files,
        "complexity": t.complexity,
        "automation_fit": t.automation_fit,
        "review_risk": t.review_risk,
        "change_scope": t.change_scope,
        "constraints": t.constraints,
        "success_criteria": t.success_criteria,
        "expected_effect": t.expected_effect,
        "depends_on": t.depends_on,
        "repair_maturity": t.repair_maturity,
    }


def _error_response(
    error_code: str,
    message: str,
    *,
    invalid_fields: list[dict[str, Any]] | None = None,
    suggested_fix: dict[str, Any] | None = None,
    recoverable: bool = True,
) -> dict[str, Any]:
    """Build a structured error response (not an exception — for tool returns)."""
    from drift.errors import ERROR_REGISTRY

    info = ERROR_REGISTRY.get(error_code)
    return {
        "schema_version": SCHEMA_VERSION,
        "type": "error",
        "error_code": error_code,
        "category": info.category if info else "input",
        "message": message,
        "invalid_fields": invalid_fields or [],
        "suggested_fix": suggested_fix,
        "recoverable": recoverable,
    }

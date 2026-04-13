"""Dependency-light finding prioritization and recommendation helpers.

These helpers are shared across API and output surfaces to avoid import
cycles between serialization layers.
"""

from __future__ import annotations

from drift.models import Finding, Severity, SignalType
from drift.recommendations import generate_recommendation

_ARCHITECTURE_BOUNDARY_SIGNALS = {
    SignalType.ARCHITECTURE_VIOLATION,
    SignalType.CIRCULAR_IMPORT,
    SignalType.CO_CHANGE_COUPLING,
    SignalType.COHESION_DEFICIT,
    SignalType.FAN_OUT_EXPLOSION,
}

_STYLE_OR_HYGIENE_SIGNALS = {
    SignalType.NAMING_CONTRACT_VIOLATION,
    SignalType.DOC_IMPL_DRIFT,
    SignalType.EXPLAINABILITY_DEFICIT,
    SignalType.BROAD_EXCEPTION_MONOCULTURE,
    SignalType.GUARD_CLAUSE_DEFICIT,
    SignalType.DEAD_CODE_ACCUMULATION,
}

_SEVERITY_RANK = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFO: 4,
}


def _dedupe_findings(ranked_findings: list[Finding]) -> tuple[list[Finding], dict[int, int]]:
    """Return canonical findings and duplicate counts keyed by canonical object id."""
    deduped: list[Finding] = []
    seen: dict[tuple[str, str, int, int, str], Finding] = {}
    duplicate_counts: dict[int, int] = {}

    for finding in ranked_findings:
        key = _finding_dedupe_key(finding)
        existing = seen.get(key)
        if existing is None:
            seen[key] = finding
            deduped.append(finding)
            duplicate_counts[id(finding)] = 1
            continue
        duplicate_counts[id(existing)] = duplicate_counts.get(id(existing), 1) + 1

    return deduped, duplicate_counts


def _finding_dedupe_key(f: Finding) -> tuple[str, str, int, int, str]:
    file_path = f.file_path.as_posix() if f.file_path else ""
    start_line = int(f.start_line or 0)
    end_line = int(f.end_line or 0)
    title = (f.title or "").strip().lower()
    rule_id = f.rule_id or f.signal_type
    return (rule_id, file_path, start_line, end_line, title)


def _priority_class(f: Finding) -> str:
    """Map finding to a decision-priority class."""
    if f.signal_type in _ARCHITECTURE_BOUNDARY_SIGNALS:
        return "architecture_boundary"
    if f.signal_type in _STYLE_OR_HYGIENE_SIGNALS:
        return "style_or_hygiene"
    return "structural_risk"


def _priority_rank(priority_class: str) -> int:
    if priority_class == "architecture_boundary":
        return 0
    if priority_class == "structural_risk":
        return 1
    return 2


def _next_step_for_finding(
    f: Finding,
    include_recommendation: bool = False,
) -> str | None:
    if include_recommendation:
        rec = generate_recommendation(f)
        if rec:
            return rec.title
    return f.fix


def _expected_benefit_for_finding(f: Finding) -> str:
    rec = generate_recommendation(f)
    if rec and rec.impact:
        return rec.impact
    if f.severity in (Severity.CRITICAL, Severity.HIGH):
        return "high"
    if f.severity == Severity.MEDIUM:
        return "medium"
    return "low"

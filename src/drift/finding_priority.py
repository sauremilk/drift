"""Dependency-light finding prioritization and recommendation helpers.

These helpers are shared across API and output surfaces to avoid import
cycles between serialization layers.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from drift.models import Finding, Severity, SignalType
from drift.recommendations import generate_recommendation

if TYPE_CHECKING:
    from drift.models import FileHistory

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


def _context_score(
    finding: Finding,
    file_history: FileHistory | None,
) -> float:
    """Return an operational-context urgency score in [0.0, 1.0].

    A higher score indicates a finding in a hotter, more actively modified,
    or more broadly owned file — making it more operationally urgent. The
    score is used as a *secondary* sort key after structural class and
    severity so it only breaks ties, preserving backwards-compatible
    class-label ordering.

    Inputs (all from ``FileHistory``):

    * ``change_frequency_30d`` — weekly change rate over the last 30 days;
      normalised at 2.0 changes/week (weight 50 %).
    * ``unique_authors`` — count of distinct authors; normalised at 5
      authors (weight 30 %).
    * ``last_modified`` — days since last commit to the file; normalised
      at 365 days (weight 20 %, higher recency → higher score).

    When *file_history* is ``None`` or a field is missing, the component
    defaults to 0.0, which leaves existing sort order unchanged.
    """
    if file_history is None:
        return 0.0

    churn = getattr(file_history, "change_frequency_30d", 0.0) or 0.0
    authors = getattr(file_history, "unique_authors", 0) or 0
    last_modified: datetime.datetime | None = getattr(file_history, "last_modified", None)

    churn_score = min(1.0, churn / 2.0)
    ownership_score = min(1.0, authors / 5.0)

    if last_modified is not None:
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        if last_modified.tzinfo is None:
            last_modified = last_modified.replace(tzinfo=datetime.timezone.utc)
        days_since = max(0.0, (now - last_modified).total_seconds() / 86400.0)
        recency_score = max(0.0, 1.0 - days_since / 365.0)
    else:
        recency_score = 0.0

    return 0.5 * churn_score + 0.3 * ownership_score + 0.2 * recency_score


def _composite_sort_key(
    finding: Finding,
    file_history: FileHistory | None = None,
    file_histories: dict[str, Any] | None = None,
) -> tuple:
    """Return a sort key that combines structural class, severity, and operational context.

    Pass *file_history* directly, or provide the full *file_histories* mapping
    by file path and let this function resolve the right entry.  When both are
    ``None``, the key degrades gracefully to the legacy ``(_priority_rank,
    _SEVERITY_RANK, -impact)`` ordering.
    """
    if file_history is None and file_histories is not None and finding.file_path is not None:
        file_history = file_histories.get(finding.file_path.as_posix())

    pclass = _priority_class(finding)
    ctx = _context_score(finding, file_history)

    # Use the string .value to stay robust against fake/duck-typed severity objects.
    severity_str = getattr(finding.severity, "value", str(finding.severity)).lower()
    _SRANK_STR = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    srank = _SRANK_STR.get(severity_str, 4)

    return (
        _priority_rank(pclass),
        srank,
        round(-ctx, 6),
        -float(finding.impact),
    )

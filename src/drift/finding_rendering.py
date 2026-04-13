"""Finding serialization and signal aggregation for API responses.

Converts ``Finding`` model objects into concise or detailed API dict
representations and provides signal-level score/count aggregation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from drift.config import DriftConfig
from drift.finding_context import classify_finding_context
from drift.finding_priority import (
    _dedupe_findings,
    _expected_benefit_for_finding,
    _next_step_for_finding,
    _priority_class,
    _priority_rank,
)
from drift.signal_mapping import _ABBREV_TO_SIGNAL, signal_abbrev

if TYPE_CHECKING:
    from drift.models import RepoAnalysis


_SEVERITY_RANK: dict[str, int] = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "info": 1,
}


def severity_rank(value: str) -> int:
    """Return numeric severity rank for cross-command comparisons."""
    return _SEVERITY_RANK.get(value, 0)


def _select_priority_findings_from_list(
    findings: list[Any],
    *,
    max_items: int,
) -> list[Any]:
    """Return deduplicated, first-run priority findings.

    Uses the same structural-first ordering as machine-readable fix-first output
    so CLI entry points do not drift apart in their recommended starting point.
    """
    deduped, _counts = _dedupe_findings(findings)
    prioritized = sorted(
        deduped,
        key=lambda f: (
            _priority_rank(_priority_class(f)),
            -severity_rank(f.severity.value),
            -float(f.impact),
            -float(f.score),
            f.signal_type,
            f.file_path.as_posix() if f.file_path else "",
            int(f.start_line or 0),
        ),
    )

    seen_file_signal: set[tuple[str, str]] = set()
    unique: list[Any] = []
    for finding in prioritized:
        file_path = finding.file_path.as_posix() if finding.file_path else ""
        key = (file_path, finding.signal_type)
        if key in seen_file_signal:
            continue
        seen_file_signal.add(key)
        unique.append(finding)
        if len(unique) >= max_items:
            break

    return unique


def select_priority_findings(analysis: RepoAnalysis, *, max_items: int = 3) -> list[Any]:
    """Return deduplicated, first-run priority findings for an analysis."""
    return _select_priority_findings_from_list(analysis.findings, max_items=max_items)


def build_first_run_summary(
    analysis: RepoAnalysis,
    *,
    max_items: int = 3,
    language: str | None = None,
) -> dict[str, Any]:
    """Build a compact first-run summary for CLI and JSON surfaces."""
    top_findings = select_priority_findings(analysis, max_items=max_items)
    lang = (language or "en").lower()
    is_german = lang.startswith("de")

    if not top_findings:
        if is_german:
            return {
                "headline": "Keine prioritaeren Strukturprobleme gefunden.",
                "why_this_matters": (
                    "Drift hat aktuell keinen unmittelbaren Fix-First-Kandidaten. "
                    "Beobachte Veraenderungen ueber Zeit statt auf einen "
                    "einzelnen Snapshot zu reagieren."
                ),
                "next_step": (
                    "Fuehre drift check --fail-on none aus, um eine "
                    "nicht-blockierende Basislinie zu setzen."
                ),
                "top_findings": [],
            }
        return {
            "headline": "No priority structural issues detected.",
            "why_this_matters": (
                "Drift did not find an immediate fix-first item. "
                "Track deltas over time instead of overreacting to a single snapshot."
            ),
            "next_step": "Run drift check --fail-on none to keep a non-blocking baseline.",
            "top_findings": [],
        }

    top_finding = top_findings[0]
    next_step = _next_step_for_finding(top_finding)
    high_or_critical = sum(
        1 for finding in analysis.findings if finding.severity.value in {"critical", "high"}
    )

    if is_german:
        headline = (
            "Starte mit dem hoechsten strukturellen Risiko."
            if high_or_critical
            else "Starte mit einem fokussierten Struktur-Fix."
        )
        why_this_matters = (
            "Ein einzelner gezielter Fix liefert schneller einen belastbaren Nutzen "
            "als die gesamte Ergebnisliste gleichzeitig anzugehen."
        )
        default_next_step = (
            "Nutze drift fix-plan --repo . --max-tasks 5 fuer konkrete "
            "Reparaturschritte."
        )
    else:
        headline = (
            "Start with the highest-risk structural issue."
            if high_or_critical
            else "Start with one focused structural fix."
        )
        why_this_matters = (
            "A single targeted repair creates a faster, more trustworthy first win "
            "than scanning the entire findings table at once."
        )
        default_next_step = "Use drift fix-plan --repo . --max-tasks 5 for concrete repair tasks."

    return {
        "headline": headline,
        "why_this_matters": why_this_matters,
        "next_step": next_step or default_next_step,
        "top_findings": [
            {
                **_finding_concise(finding),
                "priority_class": _priority_class(finding),
                "expected_benefit": _expected_benefit_for_finding(finding),
            }
            for finding in top_findings
        ],
    }


def _finding_fingerprint_value(f: Any) -> str:
    """Return deterministic fingerprint for finding-like objects used by API responses."""
    from drift.baseline import finding_fingerprint

    return finding_fingerprint(f)


def _finding_concise(f: Any) -> dict[str, Any]:
    """Minimal finding dict for concise responses."""
    signal = signal_abbrev(f.signal_type)
    severity = f.severity.value

    return {
        "signal": signal,
        "signal_abbrev": signal,
        "signal_id": signal,
        "signal_type": f.signal_type,
        "rule_id": f.rule_id,
        "severity": severity,
        "severity_rank": severity_rank(severity),
        "title": f.title,
        "file": f.file_path.as_posix() if f.file_path else None,
        "line": f.start_line,
        "finding_context": classify_finding_context(f, DriftConfig()),
        "detection_method": getattr(f, "metadata", {}).get("detection_method"),
        "fingerprint": _finding_fingerprint_value(f),
        "next_step": _next_step_for_finding(f),
    }


def _finding_detailed(f: Any, *, rank: int | None = None) -> dict[str, Any]:
    """Full finding dict for detailed responses."""
    from drift.recommendations import generate_recommendation

    rec = generate_recommendation(f)
    signal = signal_abbrev(f.signal_type)
    severity = f.severity.value
    return {
        "signal": signal,
        "signal_abbrev": signal,
        "signal_id": signal,
        "signal_type": f.signal_type,
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
        "detection_method": getattr(f, "metadata", {}).get("detection_method"),
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
    """Convert trend data to API dict."""
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
    return float(getattr(config.weights, str(sig_type), 1.0))


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
    items: list[dict[str, Any]] = []
    for idx, f in enumerate(select_priority_findings(analysis, max_items=max_items), start=1):
        signal = signal_abbrev(f.signal_type)
        severity = f.severity.value
        items.append(
            {
                "rank": idx,
                "signal": signal,
                "signal_abbrev": signal,
                "signal_id": signal,
                "signal_type": f.signal_type,
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


def _finding_guided(f: Any, *, rank: int | None = None) -> dict[str, Any]:
    """Guided-mode finding dict with plain-language text and agent prompt.

    Designed for users without architecture expertise (Persona A).
    """
    from drift.output.guided_output import plain_text_for_signal, severity_label
    from drift.output.prompt_generator import file_role_description, generate_agent_prompt

    signal = signal_abbrev(f.signal_type)
    severity = f.severity.value
    return {
        "signal": signal,
        "signal_type": f.signal_type,
        "severity_label": severity_label(severity),
        "plain_text": plain_text_for_signal(f.signal_type),
        "file_role": file_role_description(f),
        "file": f.file_path.as_posix() if f.file_path else None,
        "line": f.start_line,
        "agent_prompt": generate_agent_prompt(f),
        "fingerprint": _finding_fingerprint_value(f),
        **({"rank": rank} if rank is not None else {}),
    }

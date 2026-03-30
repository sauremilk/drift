"""JSON output for CI/CD integration."""

from __future__ import annotations

import json
from typing import Any

from drift import __version__
from drift.models import Finding, ModuleScore, RepoAnalysis, Severity, SignalType
from drift.recommendations import generate_recommendation

# JSON schema version — increment on breaking output changes.
# Major: incompatible field removals/renames.  Minor: additive new fields.
SCHEMA_VERSION = "1.0"


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


def _finding_dedupe_key(f: Finding) -> tuple[str, str, int, int, str]:
    """Build a stable key for finding deduplication in machine-readable output."""
    file_path = f.file_path.as_posix() if f.file_path else ""
    start_line = int(f.start_line or 0)
    end_line = int(f.end_line or 0)
    title = (f.title or "").strip().lower()
    rule_id = f.rule_id or f.signal_type.value
    return (rule_id, file_path, start_line, end_line, title)


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


def _next_step_for_finding(f: Finding) -> str | None:
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


def _fix_first_list(ranked_findings: list[Finding], max_items: int = 10) -> list[dict[str, Any]]:
    prioritized = sorted(
        ranked_findings,
        key=lambda f: (
            _priority_rank(_priority_class(f)),
            _SEVERITY_RANK[f.severity],
            -float(f.impact),
            -float(f.score_contribution),
            f.signal_type.value,
            f.file_path.as_posix() if f.file_path else "",
            int(f.start_line or 0),
        ),
    )

    items: list[dict[str, Any]] = []
    for idx, f in enumerate(prioritized[:max_items], start=1):
        items.append(
            {
                "rank": idx,
                "priority_class": _priority_class(f),
                "signal": f.signal_type.value,
                "rule_id": f.rule_id,
                "severity": f.severity.value,
                "impact": f.impact,
                "score_contribution": f.score_contribution,
                "title": f.title,
                "file": f.file_path.as_posix() if f.file_path else None,
                "start_line": f.start_line,
                "next_step": _next_step_for_finding(f),
                "expected_benefit": _expected_benefit_for_finding(f),
            },
        )

    return items


def _finding_sort_key(f: Finding) -> tuple[float, str, str, int, int]:
    """Stable ordering key for machine-readable finding output."""
    return (
        -float(f.impact),
        f.signal_type.value,
        f.file_path.as_posix() if f.file_path else "",
        int(f.start_line or 0),
        int(f.end_line or 0),
    )


def _finding_to_dict(f: Finding, *, impact_rank: int | None = None) -> dict[str, Any]:
    rec = generate_recommendation(f)
    d: dict[str, Any] = {
        "signal": f.signal_type.value,
        "rule_id": f.rule_id,
        "severity": f.severity.value,
        "score": f.score,
        "impact": f.impact,
        "score_contribution": f.score_contribution,
        "impact_rank": impact_rank,
        "title": f.title,
        "description": f.description,
        "fix": f.fix,
        "file": f.file_path.as_posix() if f.file_path else None,
        "start_line": f.start_line,
        "end_line": f.end_line,
        "symbol": f.symbol,
        "related_files": [rf.as_posix() for rf in f.related_files],
        "ai_attributed": f.ai_attributed,
        "deferred": f.deferred,
        "metadata": f.metadata,
        "remediation": {
            "title": rec.title,
            "description": rec.description,
            "effort": rec.effort,
            "impact": rec.impact,
        } if rec else None,
    }
    return d


def _module_to_dict(m: ModuleScore) -> dict[str, Any]:
    return {
        "path": m.path.as_posix(),
        "drift_score": m.drift_score,
        "severity": m.severity.value,
        "signal_scores": {s.value: v for s, v in m.signal_scores.items()},
        "finding_count": len(m.findings),
        "ai_ratio": m.ai_ratio,
    }


def _finding_compact_dict(
    finding: Finding,
    *,
    rank: int,
    duplicate_count: int,
) -> dict[str, Any]:
    """Compact finding shape optimized for agent/CI prioritization."""
    return {
        "rank": rank,
        "signal": finding.signal_type.value,
        "rule_id": finding.rule_id,
        "severity": finding.severity.value,
        "impact": finding.impact,
        "score_contribution": finding.score_contribution,
        "title": finding.title,
        "file": finding.file_path.as_posix() if finding.file_path else None,
        "start_line": finding.start_line,
        "duplicate_count": duplicate_count,
        "next_step": _next_step_for_finding(finding),
    }


def _analysis_status_to_dict(analysis: RepoAnalysis) -> dict[str, Any]:
    return {
        "status": analysis.analysis_status,
        "degraded": analysis.is_degraded,
        "is_fully_reliable": analysis.is_fully_reliable,
        "causes": analysis.degradation_causes,
        "affected_components": analysis.degradation_components,
        "events": analysis.degradation_events,
    }


def analysis_to_json(analysis: RepoAnalysis, indent: int = 2, compact: bool = False) -> str:
    """Serialize a RepoAnalysis to JSON string."""
    # Rank findings by impact (descending) for consumer convenience
    ranked = sorted(analysis.findings, key=_finding_sort_key)
    impact_ranks: dict[int, int] = {id(f): rank for rank, f in enumerate(ranked, 1)}

    deduped_findings, duplicate_counts = _dedupe_findings(ranked)
    compact_findings = [
        _finding_compact_dict(
            finding,
            rank=index,
            duplicate_count=duplicate_counts.get(id(finding), 1),
        )
        for index, finding in enumerate(deduped_findings, start=1)
    ]

    fix_first = _fix_first_list(deduped_findings)

    data: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "version": __version__,
        "repo": analysis.repo_path.as_posix(),
        "analyzed_at": analysis.analyzed_at.isoformat(),
        "drift_score": analysis.drift_score,
        "severity": analysis.severity.value,
        "analysis_status": _analysis_status_to_dict(analysis),
        "trend": {
            "previous_score": analysis.trend.previous_score,
            "delta": analysis.trend.delta,
            "direction": analysis.trend.direction,
            "recent_scores": analysis.trend.recent_scores,
            "history_depth": analysis.trend.history_depth,
            "transition_ratio": analysis.trend.transition_ratio,
        } if analysis.trend else None,
        "summary": {
            "total_files": analysis.total_files,
            "total_functions": analysis.total_functions,
            "ai_attributed_ratio": analysis.ai_attributed_ratio,
            "ai_tools_detected": analysis.ai_tools_detected,
            "analysis_duration_seconds": analysis.analysis_duration_seconds,
        },
        "findings_compact": compact_findings,
        "compact_summary": {
            "findings_total": len(ranked),
            "findings_deduplicated": len(deduped_findings),
            "duplicate_findings_removed": len(ranked) - len(deduped_findings),
            "critical_count": sum(1 for f in deduped_findings if f.severity == Severity.CRITICAL),
            "high_count": sum(1 for f in deduped_findings if f.severity == Severity.HIGH),
            "fix_first_count": len(fix_first),
        },
        "fix_first": fix_first,
        "suppressed_count": analysis.suppressed_count,
        "context_tagged_count": analysis.context_tagged_count,
    }

    if not compact:
        data["modules"] = [_module_to_dict(m) for m in analysis.module_scores]
        data["findings"] = [
            _finding_to_dict(f, impact_rank=impact_ranks.get(id(f)))
            for f in ranked
        ]

    return json.dumps(data, indent=indent, default=str, sort_keys=True)


def findings_to_sarif(analysis: RepoAnalysis) -> str:
    """Export findings in SARIF format for GitHub Code Scanning integration."""
    rules: list[dict[str, object]] = []
    results: list[dict[str, object]] = []

    rule_ids: dict[str, int] = {}
    for f in sorted(analysis.findings, key=_finding_sort_key):
        rule_key = f.rule_id or f.signal_type.value
        if rule_key not in rule_ids:
            rule_ids[rule_key] = len(rules)
            rule_obj: dict[str, object] = {
                "id": rule_key,
                "shortDescription": {"text": f.signal_type.value},
                "defaultConfiguration": {
                    "level": "error"
                    if f.severity in (Severity.CRITICAL, Severity.HIGH)
                    else "warning"
                    if f.severity == Severity.MEDIUM
                    else "note",
                },
            }
            # Attach CWE reference for security-related findings.
            cwe = f.metadata.get("cwe")
            if cwe and isinstance(cwe, str) and cwe.startswith("CWE-"):
                cwe_id = cwe.split("-", 1)[1]
                rule_obj["helpUri"] = (
                    f"https://cwe.mitre.org/data/definitions/{cwe_id}.html"
                )
            rules.append(rule_obj)

        result: dict[str, Any] = {
            "ruleId": rule_key,
            "message": {"text": f"{f.title}\n{f.description}"},
            "level": "error"
            if f.severity in (Severity.CRITICAL, Severity.HIGH)
            else "warning"
            if f.severity == Severity.MEDIUM
            else "note",
        }

        if f.file_path:
            location: dict[str, Any] = {
                "physicalLocation": {
                    "artifactLocation": {"uri": f.file_path.as_posix()},
                },
            }
            if f.start_line:
                location["physicalLocation"]["region"] = {
                    "startLine": f.start_line,
                }
                if f.end_line:
                    location["physicalLocation"]["region"]["endLine"] = f.end_line
            result["locations"] = [location]

        # Include all related locations (Opt-2: expose every location in SARIF)
        if f.related_files:
            result["relatedLocations"] = [
                {
                    "id": idx,
                    "message": {"text": "Related file"},
                    "physicalLocation": {
                        "artifactLocation": {"uri": rf.as_posix()},
                    },
                }
                for idx, rf in enumerate(f.related_files)
            ]

        # Include fix as a help text in the SARIF rule
        if f.fix:
            result["message"]["text"] = f"{f.title}\n{f.description}\nFIX: {f.fix}"

        # ADR-006: context tags as SARIF result properties
        ctx_tags = f.metadata.get("context_tags")
        if ctx_tags:
            result["properties"] = {"drift:context": ctx_tags}

        results.append(result)

    run_obj: dict[str, Any] = {
        "tool": {
            "driver": {
                "name": "drift",
                "version": __version__,
                "rules": rules,
            },
        },
        "results": results,
        "properties": {
            "drift:analysisStatus": {
                "status": analysis.analysis_status,
                "degraded": analysis.is_degraded,
                "isFullyReliable": analysis.is_fully_reliable,
                "causes": analysis.degradation_causes,
                "affectedComponents": analysis.degradation_components,
                "events": analysis.degradation_events,
            },
        },
    }

    # ADR-005: attach trend context as custom SARIF properties
    if analysis.trend and analysis.trend.direction != "baseline":
        run_obj["properties"]["drift:trend"] = {
            "previousScore": analysis.trend.previous_score,
            "delta": analysis.trend.delta,
            "direction": analysis.trend.direction,
        }

    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [run_obj],
    }

    return json.dumps(sarif, indent=2, default=str, sort_keys=True)

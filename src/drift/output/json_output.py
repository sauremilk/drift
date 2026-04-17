"""JSON output for CI/CD integration."""

from __future__ import annotations

import json
from typing import Any

from drift import __version__
from drift.api_helpers import (
    build_drift_score_scope,
    finding_base_payload,
    signal_abbrev,
    signal_abbrev_map,
)
from drift.baseline import finding_fingerprint
from drift.config import DriftConfig
from drift.finding_context import classify_finding_context, split_findings_by_context
from drift.finding_rendering import _select_priority_findings_from_list, build_first_run_summary
from drift.models import (
    OUTPUT_SCHEMA_VERSION,
    Finding,
    ModuleScore,
    RepoAnalysis,
    Severity,
    SignalType,
)
from drift.negative_context import findings_to_negative_context, negative_context_to_dict
from drift.recommendations import generate_recommendation

# JSON schema version — shared with API responses (ADR-042).
SCHEMA_VERSION = OUTPUT_SCHEMA_VERSION


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
    rule_id = f.rule_id or f.signal_type
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


def _fix_first_list(ranked_findings: list[Finding], max_items: int = 10) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    prioritized = _select_priority_findings_from_list(ranked_findings, max_items=max_items)
    for idx, f in enumerate(prioritized, start=1):
        items.append(
            {
                "rank": idx,
                "finding_id": finding_fingerprint(f),
                "priority_class": _priority_class(f),
                "signal": f.signal_type,
                "signal_abbrev": signal_abbrev(f.signal_type),
                "rule_id": f.rule_id,
                "severity": f.severity.value,
                "finding_context": classify_finding_context(f, DriftConfig()),
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
        f.signal_type,
        f.file_path.as_posix() if f.file_path else "",
        int(f.start_line or 0),
        int(f.end_line or 0),
    )


def _finding_to_dict(f: Finding, *, impact_rank: int | None = None) -> dict[str, Any]:
    base = finding_base_payload(f)
    rec = generate_recommendation(f)
    d: dict[str, Any] = {
        "finding_id": finding_fingerprint(f),
        "signal": f.signal_type,
        "signal_abbrev": signal_abbrev(f.signal_type),
        "rule_id": f.rule_id,
        "severity": base["severity"],
        "score": f.score,
        "impact": f.impact,
        "score_contribution": f.score_contribution,
        "impact_rank": impact_rank,
        "title": base["title"],
        "description": f.description,
        "fix": f.fix,
        "file": base["file"],
        "language": f.language,
        "start_line": base["start_line"],
        "end_line": base["end_line"],
        "finding_context": base["finding_context"],
        "symbol": f.symbol,
        "logical_location": base["logical_location"],
        "related_files": [rf.as_posix() for rf in f.related_files],
        "ai_attributed": f.ai_attributed,
        "deferred": f.deferred,
        "status": f.status.value,
        "status_set_by": f.status_set_by,
        "status_reason": f.status_reason,
        "metadata": f.metadata,
        "attribution": {
            "commit_hash": f.attribution.commit_hash,
            "author": f.attribution.author,
            "email": f.attribution.email,
            "date": f.attribution.date.isoformat(),
            "branch_hint": f.attribution.branch_hint,
            "ai_attributed": f.attribution.ai_attributed,
            "ai_confidence": f.attribution.ai_confidence,
            "commit_message": f.attribution.commit_message_summary,
        } if f.attribution else None,
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
        "signal_scores": {s: v for s, v in m.signal_scores.items()},
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
        "finding_id": finding_fingerprint(finding),
        "signal": finding.signal_type,
        "signal_abbrev": signal_abbrev(finding.signal_type),
        "rule_id": finding.rule_id,
        "severity": finding.severity.value,
        "status": finding.status.value,
        "finding_context": classify_finding_context(finding, DriftConfig()),
        "impact": finding.impact,
        "score_contribution": finding.score_contribution,
        "title": finding.title,
        "file": finding.file_path.as_posix() if finding.file_path else None,
        "language": finding.language,
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
        "skipped_languages": analysis.skipped_languages or None,
    }


def _phase_timing_summary(analysis: RepoAnalysis) -> dict[str, float]:
    phase_timings = analysis.phase_timings or {}
    return {
        "discover_seconds": round(float(phase_timings.get("discover_seconds", 0.0)), 3),
        "parse_seconds": round(float(phase_timings.get("parse_seconds", 0.0)), 3),
        "git_seconds": round(float(phase_timings.get("git_seconds", 0.0)), 3),
        "signals_seconds": round(float(phase_timings.get("signals_seconds", 0.0)), 3),
        "output_seconds": round(float(phase_timings.get("output_seconds", 0.0)), 3),
        "total_seconds": round(
            float(phase_timings.get("total_seconds", analysis.analysis_duration_seconds)),
            3,
        ),
    }


def analysis_to_json(
    analysis: RepoAnalysis,
    indent: int = 2,
    compact: bool = False,
    response_detail: str = "detailed",
    drift_score_scope: str | None = None,
    language: str | None = None,
    group_by: str | None = None,
) -> str:
    """Serialize a RepoAnalysis to JSON string."""
    # Rank findings by impact (descending) for consumer convenience
    ranked = sorted(analysis.findings, key=_finding_sort_key)
    impact_ranks: dict[int, int] = {id(f): rank for rank, f in enumerate(ranked, 1)}

    deduped_findings, duplicate_counts = _dedupe_findings(ranked)
    suppressed_ranked = sorted(analysis.suppressed_findings, key=_finding_sort_key)
    cfg = DriftConfig()
    prioritized_fix_first, excluded_fix_first, context_counts = split_findings_by_context(
        deduped_findings,
        cfg,
        include_non_operational=False,
    )
    compact_findings = [
        _finding_compact_dict(
            finding,
            rank=index,
            duplicate_count=duplicate_counts.get(id(finding), 1),
        )
        for index, finding in enumerate(deduped_findings, start=1)
    ]

    fix_first = _fix_first_list(prioritized_fix_first)

    data: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "version": __version__,
        "signal_abbrev_map": signal_abbrev_map(),
        "repo": analysis.repo_path.as_posix(),
        "analyzed_at": analysis.analyzed_at.isoformat(),
        "drift_score": round(analysis.drift_score, 3),
        "grade": analysis.grade[0],
        "grade_label": analysis.grade[1],
        "drift_score_scope": drift_score_scope or build_drift_score_scope(context="repo"),
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
            "phase_timing": _phase_timing_summary(analysis),
            "skipped_languages": analysis.skipped_languages or None,
        },
        "first_run": build_first_run_summary(
            analysis,
            max_items=3,
            language=language,
        ),
        "findings_compact": compact_findings,
        "compact_summary": {
            "findings_total": len(ranked),
            "findings_deduplicated": len(deduped_findings),
            "duplicate_findings_removed": len(ranked) - len(deduped_findings),
            "suppressed_total": len(suppressed_ranked),
            "critical_count": sum(1 for f in deduped_findings if f.severity == Severity.CRITICAL),
            "high_count": sum(1 for f in deduped_findings if f.severity == Severity.HIGH),
            "fix_first_count": len(fix_first),
        },
        "fix_first": fix_first,
        "finding_context_policy": {
            "counts": context_counts,
            "non_operational_contexts": sorted(
                set(cfg.finding_context.non_operational_contexts)
            ),
            "include_non_operational_in_fix_first": False,
            "excluded_from_fix_first": len(excluded_fix_first),
        },
        "suppressed_count": analysis.suppressed_count,
        "context_tagged_count": analysis.context_tagged_count,
        "baseline": {
            "applied": analysis.baseline_new_count is not None,
            "new_findings_count": analysis.baseline_new_count,
            "baseline_matched_count": analysis.baseline_matched_count,
        } if analysis.baseline_new_count is not None else None,
        "negative_context": [
            negative_context_to_dict(nc)
            for nc in findings_to_negative_context(analysis.findings, max_items=20)
        ],
    }

    if group_by:
        from drift.output.grouping import group_findings

        grouped = group_findings(deduped_findings, group_by)
        data["grouped_findings"] = {
            name: [
                _finding_compact_dict(f, rank=i, duplicate_count=1)
                for i, f in enumerate(items, 1)
            ]
            for name, items in grouped.items()
        }

    if not compact:
        data["modules"] = [_module_to_dict(m) for m in analysis.module_scores]
        if response_detail == "detailed":
            data["findings"] = [
                _finding_to_dict(f, impact_rank=impact_ranks.get(id(f)))
                for f in ranked
            ]
            data["findings_suppressed"] = [
                _finding_to_dict(f)
                for f in suppressed_ranked
            ]
        else:
            data["findings"] = [
                _finding_compact_dict(
                    f,
                    rank=impact_ranks.get(id(f), 0),
                    duplicate_count=duplicate_counts.get(id(f), 1),
                )
                for f in ranked
            ]
            data["findings_suppressed"] = [
                _finding_compact_dict(
                    f,
                    rank=0,
                    duplicate_count=1,
                )
                for f in suppressed_ranked
            ]

    return json.dumps(data, indent=indent, default=str, sort_keys=True)


def findings_to_sarif(analysis: RepoAnalysis) -> str:
    """Export findings in SARIF format for GitHub Code Scanning integration."""
    rules: list[dict[str, object]] = []
    results: list[dict[str, object]] = []

    rule_ids: dict[str, int] = {}
    for f in sorted(analysis.findings, key=_finding_sort_key):
        rule_key = f.rule_id or f.signal_type
        if rule_key not in rule_ids:
            rule_ids[rule_key] = len(rules)
            rule_obj: dict[str, object] = {
                "id": rule_key,
                "shortDescription": {"text": f.signal_type},
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
            # ADR-052: attach recommendation as rule-level help text.
            try:
                from drift.recommendations import generate_recommendation

                rule_rec = generate_recommendation(f)
                if rule_rec:
                    rule_obj["help"] = {
                        "text": rule_rec.description,
                        "markdown": f"**{rule_rec.title}**: {rule_rec.description}",
                    }
            except Exception:
                pass
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
            if f.start_line is not None and f.start_line > 0:
                location["physicalLocation"]["region"] = {
                    "startLine": f.start_line,
                }
                if f.end_line and f.end_line > 0:
                    location["physicalLocation"]["region"]["endLine"] = f.end_line
            else:
                # Fallback: provide startLine 1 so GitHub can create
                # file-level inline annotations (#95).
                location["physicalLocation"]["region"] = {"startLine": 1}
            result["locations"] = [location]

        # SARIF v2.1.0 §3.33: logical locations for AST-based navigation.
        if f.logical_location:
            ll: dict[str, Any] = {
                "name": f.logical_location.name,
                "kind": f.logical_location.kind,
                "fullyQualifiedName": f.logical_location.fully_qualified_name,
            }
            result["locations"] = result.get("locations", [])
            if result["locations"]:
                result["locations"][0]["logicalLocations"] = [ll]
            else:
                result["logicalLocations"] = [ll]

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

        # ADR-052: enrich message with fix text and recommendation action.
        if f.fix:
            base_text = f"{f.title}\n{f.description}\nFIX: {f.fix}"
            try:
                from drift.recommendations import generate_recommendation

                msg_rec = generate_recommendation(f)
                if msg_rec:
                    combined = f"{base_text} | {msg_rec.title}"
                    base_text = combined[:400] if len(combined) > 400 else combined
            except Exception:
                pass
            result["message"]["text"] = base_text

        # ADR-006: context tags as SARIF result properties
        props: dict[str, Any] = {}

        # ADR-042: stable finding ID for cross-referencing
        props["drift:findingId"] = finding_fingerprint(f)

        # Language annotation for multi-language repositories.
        if f.language:
            props["drift:language"] = f.language

        ctx_tags = f.metadata.get("context_tags")
        if ctx_tags:
            props["drift:context"] = ctx_tags

        # ADR-034: attribution provenance in SARIF properties
        if f.attribution:
            props["drift:attribution"] = {
                "commitHash": f.attribution.commit_hash,
                "author": f.attribution.author,
                "date": f.attribution.date.isoformat(),
                "branchHint": f.attribution.branch_hint,
                "aiAttributed": f.attribution.ai_attributed,
                "aiConfidence": f.attribution.ai_confidence,
            }

        if props:
            result["properties"] = props

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

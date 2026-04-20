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
from drift.finding_priority import (
    _dedupe_findings,
    _expected_benefit_for_finding,
    _next_step_for_finding,
    _priority_class,
)
from drift.finding_rendering import _select_priority_findings_from_list, build_first_run_summary
from drift.models import (
    OUTPUT_SCHEMA_VERSION,
    Finding,
    ModuleScore,
    RepoAnalysis,
    Severity,
)
from drift.negative_context import findings_to_negative_context, negative_context_to_dict
from drift.recommendations import generate_recommendation

# JSON schema version — shared with API responses (ADR-042).
SCHEMA_VERSION = OUTPUT_SCHEMA_VERSION


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
        "description": f.human_message or f.description,
        "human_message": f.human_message,
        "fix": f.fix,
        "root_cause": f.root_cause,
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


def _phase_timing_summary(analysis: RepoAnalysis) -> dict[str, float | dict[str, float]]:
    phase_timings = analysis.phase_timings or {}

    def _timing_value(name: str, default: float) -> float:
        value = phase_timings.get(name, default)
        if isinstance(value, (int, float)):
            return round(float(value), 3)
        return round(default, 3)

    per_signal_raw = phase_timings.get("per_signal", {})
    per_signal: dict[str, float] = {}
    if isinstance(per_signal_raw, dict):
        for key, value in per_signal_raw.items():
            if isinstance(value, (int, float)):
                per_signal[str(key)] = round(float(value), 3)

    return {
        "discover_seconds": _timing_value("discover_seconds", 0.0),
        "parse_seconds": _timing_value("parse_seconds", 0.0),
        "git_seconds": _timing_value("git_seconds", 0.0),
        "signals_seconds": _timing_value("signals_seconds", 0.0),
        "per_signal": per_signal,
        "output_seconds": _timing_value("output_seconds", 0.0),
        "total_seconds": _timing_value("total_seconds", analysis.analysis_duration_seconds),
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
        "broad_security_suppressions": list(analysis.broad_security_suppressions),
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


def _sarif_build_rule(f: Finding) -> dict[str, Any]:
    """Build a SARIF rule object for a finding."""
    rule_obj: dict[str, Any] = {
        "id": f.rule_id or f.signal_type,
        "shortDescription": {"text": f.signal_type},
        "defaultConfiguration": {
            "level": "error"
            if f.severity in (Severity.CRITICAL, Severity.HIGH)
            else "warning"
            if f.severity == Severity.MEDIUM
            else "note",
        },
    }
    cwe = f.metadata.get("cwe")
    if cwe and isinstance(cwe, str) and cwe.startswith("CWE-"):
        cwe_id = cwe.split("-", 1)[1]
        rule_obj["helpUri"] = f"https://cwe.mitre.org/data/definitions/{cwe_id}.html"
    try:
        rule_rec = generate_recommendation(f)
        if rule_rec:
            rule_obj["help"] = {
                "text": rule_rec.description,
                "markdown": f"**{rule_rec.title}**: {rule_rec.description}",
            }
    except (ImportError, AttributeError, KeyError, TypeError):
        pass
    return rule_obj


def _sarif_build_location(f: Finding) -> dict[str, Any] | None:
    """Build a SARIF physicalLocation dict for a finding, or None if no file."""
    if not f.file_path:
        return None
    location: dict[str, Any] = {
        "physicalLocation": {
            "artifactLocation": {"uri": f.file_path.as_posix()},
        },
    }
    if f.start_line is not None and f.start_line > 0:
        location["physicalLocation"]["region"] = {"startLine": f.start_line}
        if f.end_line and f.end_line > 0:
            location["physicalLocation"]["region"]["endLine"] = f.end_line
    else:
        location["physicalLocation"]["region"] = {"startLine": 1}
    return location


def _sarif_enrich_result(f: Finding, result: dict[str, Any]) -> None:
    """Enrich a SARIF result dict with location, related files, fix text, and props."""
    location = _sarif_build_location(f)
    if location:
        result["locations"] = [location]

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

    if f.related_files:
        result["relatedLocations"] = [
            {
                "id": idx,
                "message": {"text": "Related file"},
                "physicalLocation": {"artifactLocation": {"uri": rf.as_posix()}},
            }
            for idx, rf in enumerate(f.related_files)
        ]

    if f.fix:
        base_text = f"{f.title}\n{f.description}\nFIX: {f.fix}"
        try:
            msg_rec = generate_recommendation(f)
            if msg_rec:
                combined = f"{base_text} | {msg_rec.title}"
                base_text = combined[:400] if len(combined) > 400 else combined
        except (ImportError, AttributeError, KeyError, TypeError):
            pass
        result["message"]["text"] = base_text

    props: dict[str, Any] = {"drift:findingId": finding_fingerprint(f)}
    if f.language:
        props["drift:language"] = f.language
    ctx_tags = f.metadata.get("context_tags")
    if ctx_tags:
        props["drift:context"] = ctx_tags
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


def findings_to_sarif(analysis: RepoAnalysis) -> str:
    """Export findings in SARIF format for GitHub Code Scanning integration."""
    rules: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    rule_ids: dict[str, int] = {}

    for f in sorted(analysis.findings, key=_finding_sort_key):
        rule_key = f.rule_id or f.signal_type
        if rule_key not in rule_ids:
            rule_ids[rule_key] = len(rules)
            rules.append(_sarif_build_rule(f))

        result: dict[str, Any] = {
            "ruleId": rule_key,
            "message": {"text": f"{f.title}\n{f.description}"},
            "level": "error"
            if f.severity in (Severity.CRITICAL, Severity.HIGH)
            else "warning"
            if f.severity == Severity.MEDIUM
            else "note",
        }
        _sarif_enrich_result(f, result)
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

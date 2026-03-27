"""JSON output for CI/CD integration."""

from __future__ import annotations

import json
from typing import Any

from drift import __version__
from drift.models import Finding, ModuleScore, RepoAnalysis, Severity


def _finding_to_dict(f: Finding) -> dict[str, Any]:
    return {
        "signal": f.signal_type.value,
        "severity": f.severity.value,
        "score": f.score,
        "impact": f.impact,
        "title": f.title,
        "description": f.description,
        "fix": f.fix,
        "file": f.file_path.as_posix() if f.file_path else None,
        "start_line": f.start_line,
        "end_line": f.end_line,
        "related_files": [rf.as_posix() for rf in f.related_files],
        "ai_attributed": f.ai_attributed,
        "metadata": f.metadata,
    }


def _module_to_dict(m: ModuleScore) -> dict[str, Any]:
    return {
        "path": m.path.as_posix(),
        "drift_score": m.drift_score,
        "severity": m.severity.value,
        "signal_scores": {s.value: v for s, v in m.signal_scores.items()},
        "finding_count": len(m.findings),
        "ai_ratio": m.ai_ratio,
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


def analysis_to_json(analysis: RepoAnalysis, indent: int = 2) -> str:
    """Serialize a RepoAnalysis to JSON string."""
    data: dict[str, Any] = {
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
            "analysis_duration_seconds": analysis.analysis_duration_seconds,
        },
        "modules": [_module_to_dict(m) for m in analysis.module_scores],
        "findings": [_finding_to_dict(f) for f in analysis.findings],
        "suppressed_count": analysis.suppressed_count,
        "context_tagged_count": analysis.context_tagged_count,
    }

    return json.dumps(data, indent=indent, default=str)


def findings_to_sarif(analysis: RepoAnalysis) -> str:
    """Export findings in SARIF format for GitHub Code Scanning integration."""
    rules: list[dict[str, object]] = []
    results: list[dict[str, object]] = []

    rule_ids: dict[str, int] = {}
    for f in analysis.findings:
        rule_key = f.signal_type.value
        if rule_key not in rule_ids:
            rule_ids[rule_key] = len(rules)
            rules.append(
                {
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
            )

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
                }
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
            }
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
            }
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

    return json.dumps(sarif, indent=2, default=str)

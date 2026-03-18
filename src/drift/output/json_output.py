"""JSON output for CI/CD integration."""

from __future__ import annotations

import json
from typing import Any

from drift.models import Finding, ModuleScore, RepoAnalysis, Severity


def _finding_to_dict(f: Finding) -> dict[str, Any]:
    return {
        "signal": f.signal_type.value,
        "severity": f.severity.value,
        "score": f.score,
        "title": f.title,
        "description": f.description,
        "file": f.file_path.as_posix() if f.file_path else None,
        "start_line": f.start_line,
        "end_line": f.end_line,
        "ai_attributed": f.ai_attributed,
        "canonical_ref": f.canonical_ref,
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


def analysis_to_json(analysis: RepoAnalysis, indent: int = 2) -> str:
    """Serialize a RepoAnalysis to JSON string."""
    data: dict[str, Any] = {
        "version": "0.1.0",
        "repo": analysis.repo_path.as_posix(),
        "analyzed_at": analysis.analyzed_at.isoformat(),
        "drift_score": analysis.drift_score,
        "severity": analysis.severity.value,
        "summary": {
            "total_files": analysis.total_files,
            "total_functions": analysis.total_functions,
            "ai_attributed_ratio": analysis.ai_attributed_ratio,
            "analysis_duration_seconds": analysis.analysis_duration_seconds,
        },
        "modules": [_module_to_dict(m) for m in analysis.module_scores],
        "findings": [_finding_to_dict(f) for f in analysis.findings],
    }

    return json.dumps(data, indent=indent, default=str)


def findings_to_sarif(analysis: RepoAnalysis) -> str:
    """Export findings in SARIF format for GitHub Code Scanning integration."""
    rules = []
    results = []

    rule_ids: dict[str, int] = {}
    for f in analysis.findings:
        rule_key = f"{f.signal_type.value}/{f.severity.value}"
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

        results.append(result)

    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "drift",
                        "version": "0.1.0",
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }

    return json.dumps(sarif, indent=2, default=str)

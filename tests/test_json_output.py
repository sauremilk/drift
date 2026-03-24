"""Unit tests for JSON/SARIF output serialization."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

from drift.models import Finding, ModuleScore, RepoAnalysis, Severity, SignalType
from drift.output.json_output import analysis_to_json, findings_to_sarif


def _sample_finding(*, with_file: bool = True) -> Finding:
    return Finding(
        signal_type=SignalType.SYSTEM_MISALIGNMENT,
        severity=Severity.HIGH,
        score=0.82,
        title="Runtime config mismatch",
        description="Detected environment-specific branch logic.",
        file_path=Path("src/app/service.py") if with_file else None,
        start_line=12 if with_file else None,
        end_line=29 if with_file else None,
        related_files=[Path("src/app/config.py"), Path("src/app/settings.py")],
        ai_attributed=True,
        fix="Normalize environment access through one adapter.",
        impact=0.61,
    )


def _sample_analysis() -> RepoAnalysis:
    finding = _sample_finding()
    module = ModuleScore(
        path=Path("src/app"),
        drift_score=0.73,
        signal_scores={SignalType.SYSTEM_MISALIGNMENT: 0.73},
        findings=[finding],
        ai_ratio=1.0,
    )
    return RepoAnalysis(
        repo_path=Path("."),
        analyzed_at=datetime.datetime(2026, 1, 2, 10, 30, tzinfo=datetime.UTC),
        drift_score=0.73,
        module_scores=[module],
        findings=[finding],
        total_files=12,
        total_functions=48,
        ai_attributed_ratio=0.25,
        analysis_duration_seconds=2.3,
    )


def test_analysis_to_json_contains_expected_structure() -> None:
    analysis = _sample_analysis()

    rendered = analysis_to_json(analysis)
    payload = json.loads(rendered)

    assert payload["repo"] == "."
    assert payload["drift_score"] == 0.73
    assert payload["severity"] == "high"
    assert payload["summary"]["total_files"] == 12
    assert payload["summary"]["total_functions"] == 48
    assert payload["modules"][0]["path"] == "src/app"
    assert payload["findings"][0]["signal"] == "system_misalignment"
    assert payload["findings"][0]["file"] == "src/app/service.py"


def test_findings_to_sarif_deduplicates_rules_and_sets_levels() -> None:
    finding_one = _sample_finding()
    finding_two = _sample_finding()
    finding_two.file_path = Path("src/app/other.py")
    analysis = _sample_analysis()
    analysis.findings = [finding_one, finding_two]

    sarif = json.loads(findings_to_sarif(analysis))
    run = sarif["runs"][0]

    assert len(run["tool"]["driver"]["rules"]) == 1
    assert len(run["results"]) == 2
    assert run["results"][0]["level"] == "error"
    assert run["results"][0]["locations"][0]["physicalLocation"]["region"]["startLine"] == 12


def test_findings_to_sarif_handles_finding_without_file_path() -> None:
    finding = _sample_finding(with_file=False)
    analysis = _sample_analysis()
    analysis.findings = [finding]

    sarif = json.loads(findings_to_sarif(analysis))
    result = sarif["runs"][0]["results"][0]

    assert "locations" not in result
    assert result["ruleId"] == "system_misalignment/high"
    assert "FIX:" in result["message"]["text"]

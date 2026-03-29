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
    assert payload["analysis_status"]["status"] == "complete"
    assert payload["analysis_status"]["is_fully_reliable"] is True
    assert payload["summary"]["total_files"] == 12
    assert payload["summary"]["total_functions"] == 48
    assert payload["modules"][0]["path"] == "src/app"
    assert payload["findings"][0]["signal"] == "system_misalignment"
    assert payload["findings"][0]["file"] == "src/app/service.py"
    assert payload["findings"][0]["remediation"] is not None
    assert payload["findings"][0]["remediation"]["effort"] in {"low", "medium", "high"}
    assert isinstance(payload["fix_first"], list)
    assert payload["fix_first"]
    assert payload["fix_first"][0]["rank"] == 1


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
    assert run["properties"]["drift:analysisStatus"]["status"] == "complete"


def test_analysis_to_json_exposes_degraded_status() -> None:
    analysis = _sample_analysis()
    analysis.analysis_status = "degraded"
    analysis.degradation_causes = ["signal_failure"]
    analysis.degradation_components = ["signal:test"]
    analysis.degradation_events = [{
        "cause": "signal_failure",
        "component": "signal:test",
        "message": "Signal failed.",
    }]

    payload = json.loads(analysis_to_json(analysis))

    assert payload["analysis_status"]["status"] == "degraded"
    assert payload["analysis_status"]["degraded"] is True
    assert payload["analysis_status"]["is_fully_reliable"] is False
    assert payload["analysis_status"]["causes"] == ["signal_failure"]


def test_findings_to_sarif_handles_finding_without_file_path() -> None:
    finding = _sample_finding(with_file=False)
    analysis = _sample_analysis()
    analysis.findings = [finding]

    sarif = json.loads(findings_to_sarif(analysis))
    result = sarif["runs"][0]["results"][0]

    assert "locations" not in result
    assert result["ruleId"] == "system_misalignment"
    assert "FIX:" in result["message"]["text"]


def test_analysis_to_json_orders_findings_deterministically() -> None:
    first = _sample_finding()
    first.file_path = Path("src/a.py")
    first.start_line = 10
    first.end_line = 11
    first.impact = 0.5

    second = _sample_finding()
    second.file_path = Path("src/b.py")
    second.start_line = 10
    second.end_line = 11
    second.impact = 0.5

    analysis_one = _sample_analysis()
    analysis_one.findings = [second, first]

    analysis_two = _sample_analysis()
    analysis_two.findings = [first, second]

    payload_one = json.loads(analysis_to_json(analysis_one))
    payload_two = json.loads(analysis_to_json(analysis_two))

    files_one = [f["file"] for f in payload_one["findings"]]
    files_two = [f["file"] for f in payload_two["findings"]]

    assert files_one == ["src/a.py", "src/b.py"]
    assert files_two == ["src/a.py", "src/b.py"]


def test_fix_first_prioritizes_architecture_boundary() -> None:
    architecture = Finding(
        signal_type=SignalType.ARCHITECTURE_VIOLATION,
        severity=Severity.MEDIUM,
        score=0.51,
        title="Layer boundary violation",
        description="Service imports API layer.",
        file_path=Path("src/core/service.py"),
        start_line=20,
        fix="Move dependency behind interface.",
        impact=0.4,
    )
    style = Finding(
        signal_type=SignalType.NAMING_CONTRACT_VIOLATION,
        severity=Severity.HIGH,
        score=0.8,
        title="Inconsistent naming",
        description="Method does not follow naming contract.",
        file_path=Path("src/core/naming.py"),
        start_line=10,
        impact=0.7,
    )

    analysis = _sample_analysis()
    analysis.findings = [style, architecture]

    payload = json.loads(analysis_to_json(analysis))

    assert payload["fix_first"][0]["signal"] == "architecture_violation"
    assert payload["fix_first"][0]["priority_class"] == "architecture_boundary"

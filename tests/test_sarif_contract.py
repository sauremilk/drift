"""Contract test: SARIF output conforms to SARIF 2.1.0 structural schema.

Validates that drift's SARIF output matches the OASIS SARIF 2.1.0 specification
structure. This is a contract test — it ensures the output format stays stable
for consumers (GitHub Code Scanning, VS Code SARIF Viewer, etc.).
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

import pytest

from drift.models import Finding, ModuleScore, RepoAnalysis, Severity, SignalType
from drift.output.json_output import findings_to_sarif

pytestmark = pytest.mark.contract


def _make_finding(**overrides: Any) -> Finding:
    defaults: dict[str, Any] = dict(
        signal_type=SignalType.PATTERN_FRAGMENTATION,
        severity=Severity.HIGH,
        score=0.75,
        title="Fragmented pattern",
        description="Multiple implementations exist.",
        file_path=Path("src/app/service.py"),
        start_line=10,
        end_line=20,
        fix="Consolidate into single implementation.",
        impact=0.6,
    )
    defaults.update(overrides)
    return Finding(**defaults)


def _make_analysis(findings: list[Finding] | None = None) -> RepoAnalysis:
    findings = findings or [_make_finding()]
    module = ModuleScore(
        path=Path("src/app"),
        drift_score=0.7,
        signal_scores={SignalType.PATTERN_FRAGMENTATION: 0.7},
        findings=findings,
        ai_ratio=0.0,
    )
    return RepoAnalysis(
        repo_path=Path("."),
        analyzed_at=datetime.datetime(2026, 3, 1, tzinfo=datetime.UTC),
        drift_score=0.7,
        module_scores=[module],
        findings=findings,
        total_files=10,
        total_functions=30,
        ai_attributed_ratio=0.0,
        analysis_duration_seconds=1.0,
    )


class TestSarifSchemaContract:
    """Structural contract tests for SARIF 2.1.0 output."""

    def test_top_level_structure(self) -> None:
        sarif = json.loads(findings_to_sarif(_make_analysis()))

        assert sarif["$schema"].endswith("sarif-schema-2.1.0.json")
        assert sarif["version"] == "2.1.0"
        assert isinstance(sarif["runs"], list)
        assert len(sarif["runs"]) == 1

    def test_run_has_tool_and_results(self) -> None:
        sarif = json.loads(findings_to_sarif(_make_analysis()))
        run = sarif["runs"][0]

        assert "tool" in run
        assert "driver" in run["tool"]
        assert "results" in run
        assert isinstance(run["results"], list)

    def test_driver_has_required_fields(self) -> None:
        sarif = json.loads(findings_to_sarif(_make_analysis()))
        driver = sarif["runs"][0]["tool"]["driver"]

        assert driver["name"] == "drift"
        assert "version" in driver
        assert isinstance(driver["rules"], list)

    def test_rule_has_id_and_short_description(self) -> None:
        sarif = json.loads(findings_to_sarif(_make_analysis()))
        rules = sarif["runs"][0]["tool"]["driver"]["rules"]

        assert len(rules) >= 1
        for rule in rules:
            assert "id" in rule
            assert isinstance(rule["id"], str)
            assert "shortDescription" in rule
            assert "text" in rule["shortDescription"]
            assert "defaultConfiguration" in rule
            assert rule["defaultConfiguration"]["level"] in ("error", "warning", "note")

    def test_result_has_rule_id_message_and_level(self) -> None:
        sarif = json.loads(findings_to_sarif(_make_analysis()))
        results = sarif["runs"][0]["results"]

        assert len(results) >= 1
        for result in results:
            assert "ruleId" in result
            assert "message" in result
            assert "text" in result["message"]
            assert result["level"] in ("error", "warning", "note")

    def test_location_format(self) -> None:
        sarif = json.loads(findings_to_sarif(_make_analysis()))
        result = sarif["runs"][0]["results"][0]

        assert "locations" in result
        loc = result["locations"][0]
        phys = loc["physicalLocation"]
        assert "artifactLocation" in phys
        assert "uri" in phys["artifactLocation"]
        assert "region" in phys
        assert "startLine" in phys["region"]
        assert isinstance(phys["region"]["startLine"], int)

    def test_severity_mapping_high_to_error(self) -> None:
        finding = _make_finding(severity=Severity.HIGH)
        sarif = json.loads(findings_to_sarif(_make_analysis([finding])))
        assert sarif["runs"][0]["results"][0]["level"] == "error"

    def test_severity_mapping_medium_to_warning(self) -> None:
        finding = _make_finding(severity=Severity.MEDIUM)
        sarif = json.loads(findings_to_sarif(_make_analysis([finding])))
        assert sarif["runs"][0]["results"][0]["level"] == "warning"

    def test_severity_mapping_low_to_note(self) -> None:
        finding = _make_finding(severity=Severity.LOW)
        sarif = json.loads(findings_to_sarif(_make_analysis([finding])))
        assert sarif["runs"][0]["results"][0]["level"] == "note"

    def test_cwe_produces_help_uri(self) -> None:
        finding = _make_finding(metadata={"cwe": "CWE-862"})
        sarif = json.loads(findings_to_sarif(_make_analysis([finding])))
        rule = sarif["runs"][0]["tool"]["driver"]["rules"][0]
        assert rule["helpUri"] == "https://cwe.mitre.org/data/definitions/862.html"

    def test_analysis_status_in_run_properties(self) -> None:
        sarif = json.loads(findings_to_sarif(_make_analysis()))
        props = sarif["runs"][0]["properties"]

        assert "drift:analysisStatus" in props
        status = props["drift:analysisStatus"]
        assert "status" in status
        assert "degraded" in status
        assert "isFullyReliable" in status

    def test_related_locations_format(self) -> None:
        finding = _make_finding(
            related_files=[Path("src/app/config.py"), Path("src/app/utils.py")],
        )
        sarif = json.loads(findings_to_sarif(_make_analysis([finding])))
        result = sarif["runs"][0]["results"][0]

        assert "relatedLocations" in result
        for rl in result["relatedLocations"]:
            assert "id" in rl
            assert "message" in rl
            assert "physicalLocation" in rl
            assert "artifactLocation" in rl["physicalLocation"]

    def test_multiple_findings_deduplicate_rules(self) -> None:
        f1 = _make_finding(file_path=Path("a.py"))
        f2 = _make_finding(file_path=Path("b.py"))
        sarif = json.loads(findings_to_sarif(_make_analysis([f1, f2])))

        rules = sarif["runs"][0]["tool"]["driver"]["rules"]
        results = sarif["runs"][0]["results"]
        assert len(rules) == 1
        assert len(results) == 2

    def test_fix_included_in_message(self) -> None:
        finding = _make_finding(fix="Refactor this module.")
        sarif = json.loads(findings_to_sarif(_make_analysis([finding])))
        text = sarif["runs"][0]["results"][0]["message"]["text"]
        assert "FIX:" in text

    def test_output_is_valid_json(self) -> None:
        raw = findings_to_sarif(_make_analysis())
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)

    def test_no_finding_without_file_has_locations(self) -> None:
        finding = _make_finding(file_path=None, start_line=None, end_line=None)
        sarif = json.loads(findings_to_sarif(_make_analysis([finding])))
        result = sarif["runs"][0]["results"][0]
        assert "locations" not in result

"""Tests for ``drift import`` command and external report adapters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from drift.cli import main
from drift.ingestion.external_report import SUPPORTED_FORMATS, load_external_report
from drift.models import Severity

# ---------------------------------------------------------------------------
# Adapter unit tests
# ---------------------------------------------------------------------------


class TestSonarQubeAdapter:
    """Test SonarQube JSON adapter."""

    def test_empty_report(self, tmp_path: Path) -> None:
        report = tmp_path / "sonar.json"
        report.write_text('{"issues": []}', encoding="utf-8")
        findings = load_external_report(report, "sonarqube")
        assert findings == []

    def test_single_issue(self, tmp_path: Path) -> None:
        data = {
            "issues": [
                {
                    "key": "AX1",
                    "rule": "python:S1192",
                    "severity": "MAJOR",
                    "component": "myproject:src/app.py",
                    "message": "String duplicated 3 times",
                    "type": "CODE_SMELL",
                    "textRange": {"startLine": 10, "endLine": 12},
                }
            ]
        }
        report = tmp_path / "sonar.json"
        report.write_text(json.dumps(data), encoding="utf-8")
        findings = load_external_report(report, "sonarqube")
        assert len(findings) == 1
        f = findings[0]
        assert f.signal_type == "sonarqube:python:S1192"
        assert f.severity == Severity.MEDIUM
        assert f.file_path == Path("src/app.py")
        assert f.start_line == 10
        assert f.end_line == 12
        assert f.metadata["source"] == "sonarqube"
        assert f.metadata["external_rule"] == "python:S1192"

    def test_severity_mapping(self, tmp_path: Path) -> None:
        for sq_sev, expected in [
            ("BLOCKER", Severity.CRITICAL),
            ("CRITICAL", Severity.HIGH),
            ("MAJOR", Severity.MEDIUM),
            ("MINOR", Severity.LOW),
            ("INFO", Severity.INFO),
        ]:
            data = {"issues": [{"severity": sq_sev, "message": "test", "rule": "r"}]}
            report = tmp_path / "sonar.json"
            report.write_text(json.dumps(data), encoding="utf-8")
            findings = load_external_report(report, "sonarqube")
            assert findings[0].severity == expected, f"Failed for {sq_sev}"


class TestPylintAdapter:
    """Test pylint JSON adapter."""

    def test_empty_report(self, tmp_path: Path) -> None:
        report = tmp_path / "pylint.json"
        report.write_text("[]", encoding="utf-8")
        findings = load_external_report(report, "pylint")
        assert findings == []

    def test_single_message(self, tmp_path: Path) -> None:
        data = [
            {
                "type": "error",
                "module": "mymodule",
                "obj": "MyClass.method",
                "line": 42,
                "endLine": 44,
                "column": 0,
                "path": "src/mymodule.py",
                "symbol": "no-member",
                "message-id": "E1101",
                "message": "Instance has no 'foo' member",
            }
        ]
        report = tmp_path / "pylint.json"
        report.write_text(json.dumps(data), encoding="utf-8")
        findings = load_external_report(report, "pylint")
        assert len(findings) == 1
        f = findings[0]
        assert f.signal_type == "pylint:no-member"
        assert f.severity == Severity.HIGH
        assert f.file_path == Path("src/mymodule.py")
        assert f.start_line == 42
        assert f.symbol == "MyClass.method"
        assert f.metadata["source"] == "pylint"
        assert f.metadata["external_id"] == "E1101"

    def test_severity_mapping(self, tmp_path: Path) -> None:
        for pl_type, expected in [
            ("fatal", Severity.CRITICAL),
            ("error", Severity.HIGH),
            ("warning", Severity.MEDIUM),
            ("convention", Severity.LOW),
            ("refactor", Severity.LOW),
        ]:
            data = [{"type": pl_type, "message": "test", "path": "x.py"}]
            report = tmp_path / "pylint.json"
            report.write_text(json.dumps(data), encoding="utf-8")
            findings = load_external_report(report, "pylint")
            assert findings[0].severity == expected, f"Failed for {pl_type}"


class TestCodeClimateAdapter:
    """Test CodeClimate JSON adapter."""

    def test_empty_report(self, tmp_path: Path) -> None:
        report = tmp_path / "cc.json"
        report.write_text("[]", encoding="utf-8")
        findings = load_external_report(report, "codeclimate")
        assert findings == []

    def test_single_issue(self, tmp_path: Path) -> None:
        data = [
            {
                "check_name": "complexity",
                "description": "Function is too complex",
                "severity": "major",
                "fingerprint": "abc123",
                "categories": ["Complexity"],
                "location": {"path": "lib/helpers.py", "lines": {"begin": 5, "end": 20}},
            }
        ]
        report = tmp_path / "cc.json"
        report.write_text(json.dumps(data), encoding="utf-8")
        findings = load_external_report(report, "codeclimate")
        assert len(findings) == 1
        f = findings[0]
        assert f.signal_type == "codeclimate:complexity"
        assert f.severity == Severity.MEDIUM
        assert f.file_path == Path("lib/helpers.py")
        assert f.start_line == 5
        assert f.end_line == 20
        assert f.metadata["source"] == "codeclimate"
        assert f.metadata["external_fingerprint"] == "abc123"


class TestLoadExternalReport:
    """Test public load API."""

    def test_unsupported_format(self, tmp_path: Path) -> None:
        report = tmp_path / "report.json"
        report.write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported format"):
            load_external_report(report, "unknown")

    def test_invalid_json(self, tmp_path: Path) -> None:
        report = tmp_path / "bad.json"
        report.write_text("not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_external_report(report, "sonarqube")

    def test_supported_formats_list(self) -> None:
        assert "sonarqube" in SUPPORTED_FORMATS
        assert "pylint" in SUPPORTED_FORMATS
        assert "codeclimate" in SUPPORTED_FORMATS


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestImportCLI:
    """Test ``drift import`` CLI command."""

    def test_help_shows_formats(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["import", "--help"])
        assert result.exit_code == 0
        assert "sonarqube" in result.output
        assert "pylint" in result.output
        assert "codeclimate" in result.output

    def test_import_sonarqube_json_output(self, tmp_repo: Path) -> None:
        report = tmp_repo / "sonar.json"
        data = {
            "issues": [
                {
                    "key": "K1",
                    "rule": "python:S100",
                    "severity": "MINOR",
                    "component": "proj:main.py",
                    "message": "Rename this function",
                }
            ]
        }
        report.write_text(json.dumps(data), encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["import", str(report), "--format", "sonarqube", "--repo", str(tmp_repo), "--json"],
        )
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["external_tool"] == "sonarqube"
        assert output["external_findings_count"] == 1
        assert isinstance(output["drift_findings_count"], int)

    def test_import_empty_pylint_report(self, tmp_repo: Path) -> None:
        report = tmp_repo / "pylint.json"
        report.write_text("[]", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["import", str(report), "--format", "pylint", "--repo", str(tmp_repo), "--json"],
        )
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["external_findings_count"] == 0

    def test_import_invalid_json_fails(self, tmp_repo: Path) -> None:
        report = tmp_repo / "bad.json"
        report.write_text("not json at all", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["import", str(report), "--format", "sonarqube", "--repo", str(tmp_repo)],
        )
        assert result.exit_code != 0

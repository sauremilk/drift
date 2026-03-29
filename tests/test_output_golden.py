"""Golden / snapshot tests for JSON and SARIF output stability.

These matter because downstream CI integrations (GitHub Code Scanning,
SARIF viewers, JSON consumers) break if the output schema changes
without notice.  Golden tests lock the structure so regressions in
field names, nesting, or severity mapping are caught immediately.

Also covers previously untested SARIF branch paths:
- Findings with no file_path
- Findings with start_line but no end_line
- Findings with both start_line and end_line
- Findings with related_files
- Findings with fix text
"""

import datetime
import json
from pathlib import Path

from drift.models import (
    Finding,
    ModuleScore,
    RepoAnalysis,
    Severity,
    SignalType,
)
from drift.output.json_output import analysis_to_json, findings_to_sarif


def _minimal_analysis(**overrides) -> RepoAnalysis:
    defaults = {
        "repo_path": Path("/tmp/test-repo"),
        "analyzed_at": datetime.datetime(2026, 1, 15, 12, 0, 0),
        "drift_score": 0.42,
        "total_files": 10,
        "total_functions": 50,
        "ai_attributed_ratio": 0.3,
        "analysis_duration_seconds": 1.5,
    }
    defaults.update(overrides)
    return RepoAnalysis(**defaults)


def _finding(**overrides) -> Finding:
    defaults = {
        "signal_type": SignalType.PATTERN_FRAGMENTATION,
        "severity": Severity.MEDIUM,
        "score": 0.55,
        "title": "Test finding",
        "description": "A test finding description",
        "file_path": Path("src/module.py"),
        "start_line": 42,
    }
    defaults.update(overrides)
    return Finding(**defaults)


# ── JSON output golden structure ──────────────────────────────────────────


class TestJsonOutputGolden:
    def test_top_level_keys(self) -> None:
        """JSON output must contain exactly these top-level keys."""
        analysis = _minimal_analysis()
        data = json.loads(analysis_to_json(analysis))
        expected_keys = {
            "schema_version",
            "version",
            "repo",
            "analyzed_at",
            "drift_score",
            "severity",
            "analysis_status",
            "trend",
            "summary",
            "modules",
            "findings",
            "fix_first",
            "suppressed_count",
            "context_tagged_count",
        }
        assert set(data.keys()) == expected_keys

    def test_summary_keys(self) -> None:
        analysis = _minimal_analysis()
        data = json.loads(analysis_to_json(analysis))
        expected_summary_keys = {
            "total_files",
            "total_functions",
            "ai_attributed_ratio",
            "ai_tools_detected",
            "analysis_duration_seconds",
        }
        assert set(data["summary"].keys()) == expected_summary_keys

    def test_finding_keys(self) -> None:
        """Each finding dict must have the expected field set."""
        f = _finding()
        analysis = _minimal_analysis(findings=[f])
        data = json.loads(analysis_to_json(analysis))

        expected_finding_keys = {
            "signal",
            "rule_id",
            "severity",
            "score",
            "impact",
            "score_contribution",
            "impact_rank",
            "title",
            "description",
            "fix",
            "remediation",
            "file",
            "start_line",
            "end_line",
            "symbol",
            "related_files",
            "ai_attributed",
            "deferred",
            "metadata",
        }
        assert set(data["findings"][0].keys()) == expected_finding_keys

    def test_module_keys(self) -> None:
        ms = ModuleScore(
            path=Path("src"),
            drift_score=0.5,
            signal_scores={SignalType.PATTERN_FRAGMENTATION: 0.4},
            findings=[_finding()],
            ai_ratio=0.2,
        )
        analysis = _minimal_analysis(module_scores=[ms])
        data = json.loads(analysis_to_json(analysis))

        expected_module_keys = {
            "path",
            "drift_score",
            "severity",
            "signal_scores",
            "finding_count",
            "ai_ratio",
        }
        assert set(data["modules"][0].keys()) == expected_module_keys

    def test_severity_values_are_strings(self) -> None:
        analysis = _minimal_analysis(findings=[_finding(severity=Severity.CRITICAL)])
        data = json.loads(analysis_to_json(analysis))
        assert data["findings"][0]["severity"] == "critical"
        assert data["severity"] in ("info", "low", "medium", "high", "critical")

    def test_finding_with_no_file_path(self) -> None:
        f = _finding(file_path=None, start_line=None)
        analysis = _minimal_analysis(findings=[f])
        data = json.loads(analysis_to_json(analysis))
        assert data["findings"][0]["file"] is None

    def test_json_is_valid_json(self) -> None:
        analysis = _minimal_analysis(findings=[_finding()])
        raw = analysis_to_json(analysis)
        # Must not raise
        json.loads(raw)


# ── SARIF output golden structure ─────────────────────────────────────────


class TestSarifOutputGolden:
    def test_sarif_schema_version(self) -> None:
        analysis = _minimal_analysis(findings=[_finding()])
        data = json.loads(findings_to_sarif(analysis))
        assert data["version"] == "2.1.0"
        assert "$schema" in data

    def test_sarif_has_runs(self) -> None:
        analysis = _minimal_analysis(findings=[_finding()])
        data = json.loads(findings_to_sarif(analysis))
        assert len(data["runs"]) == 1
        run = data["runs"][0]
        assert run["tool"]["driver"]["name"] == "drift"
        assert "rules" in run["tool"]["driver"]
        assert "results" in run

    def test_sarif_finding_with_location(self) -> None:
        f = _finding(start_line=10, end_line=20)
        analysis = _minimal_analysis(findings=[f])
        data = json.loads(findings_to_sarif(analysis))
        result = data["runs"][0]["results"][0]
        assert "locations" in result
        region = result["locations"][0]["physicalLocation"]["region"]
        assert region["startLine"] == 10
        assert region["endLine"] == 20

    def test_sarif_finding_start_line_only(self) -> None:
        f = _finding(start_line=10, end_line=None)
        analysis = _minimal_analysis(findings=[f])
        data = json.loads(findings_to_sarif(analysis))
        result = data["runs"][0]["results"][0]
        region = result["locations"][0]["physicalLocation"]["region"]
        assert region["startLine"] == 10
        assert "endLine" not in region

    def test_sarif_finding_no_location(self) -> None:
        """Finding without file_path → no locations in SARIF result."""
        f = _finding(file_path=None, start_line=None)
        analysis = _minimal_analysis(findings=[f])
        data = json.loads(findings_to_sarif(analysis))
        result = data["runs"][0]["results"][0]
        assert "locations" not in result

    def test_sarif_related_files(self) -> None:
        f = _finding(related_files=[Path("src/a.py"), Path("src/b.py")])
        analysis = _minimal_analysis(findings=[f])
        data = json.loads(findings_to_sarif(analysis))
        result = data["runs"][0]["results"][0]
        assert "relatedLocations" in result
        assert len(result["relatedLocations"]) == 2

    def test_sarif_fix_text_included(self) -> None:
        f = _finding(fix="Extract shared helper")
        analysis = _minimal_analysis(findings=[f])
        data = json.loads(findings_to_sarif(analysis))
        result = data["runs"][0]["results"][0]
        assert "FIX:" in result["message"]["text"]

    def test_sarif_severity_mapping(self) -> None:
        """SARIF level: CRITICAL/HIGH → error, MEDIUM → warning, else → note."""
        for sev, expected_level in [
            (Severity.CRITICAL, "error"),
            (Severity.HIGH, "error"),
            (Severity.MEDIUM, "warning"),
            (Severity.LOW, "note"),
            (Severity.INFO, "note"),
        ]:
            f = _finding(severity=sev)
            analysis = _minimal_analysis(findings=[f])
            data = json.loads(findings_to_sarif(analysis))
            result = data["runs"][0]["results"][0]
            assert result["level"] == expected_level, f"severity={sev} → expected {expected_level}"

    def test_sarif_rule_deduplication(self) -> None:
        """Two findings with same signal+severity → one rule, two results."""
        f1 = _finding(title="A")
        f2 = _finding(title="B")
        analysis = _minimal_analysis(findings=[f1, f2])
        data = json.loads(findings_to_sarif(analysis))
        run = data["runs"][0]
        assert len(run["results"]) == 2
        assert len(run["tool"]["driver"]["rules"]) == 1

    def test_sarif_is_valid_json(self) -> None:
        analysis = _minimal_analysis(findings=[_finding()])
        raw = findings_to_sarif(analysis)
        json.loads(raw)

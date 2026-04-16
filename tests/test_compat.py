"""Tests for drop-in compatibility features.

Covers: --output-format alias, --exit-zero, --select/--ignore,
github annotation format, pyproject.toml config loading.
"""

from __future__ import annotations

import datetime
import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from drift.config import (
    SIGNAL_ABBREV,
    DriftConfig,
    SignalWeights,
    apply_signal_filter,
    resolve_signal_names,
)

# ---------------------------------------------------------------------------
# Signal abbreviation map
# ---------------------------------------------------------------------------


class TestSignalAbbrev:
    def test_all_weights_have_abbreviation(self):
        """Every weight in SignalWeights should have a corresponding abbreviation."""
        known_weights = set(SignalWeights.model_fields.keys())
        abbrev_values = set(SIGNAL_ABBREV.values())
        assert abbrev_values == known_weights

    def test_abbreviations_are_uppercase(self):
        for abbrev in SIGNAL_ABBREV:
            assert abbrev == abbrev.upper()
            assert len(abbrev) == 3


class TestResolveSignalNames:
    def test_resolve_abbreviation(self):
        assert resolve_signal_names("PFS") == ["pattern_fragmentation"]

    def test_resolve_full_name(self):
        assert resolve_signal_names("pattern_fragmentation") == ["pattern_fragmentation"]

    def test_resolve_comma_separated(self):
        result = resolve_signal_names("PFS,AVS,MDS")
        assert result == [
            "pattern_fragmentation",
            "architecture_violation",
            "mutant_duplicate",
        ]

    def test_resolve_with_spaces(self):
        result = resolve_signal_names("PFS , AVS")
        assert result == ["pattern_fragmentation", "architecture_violation"]

    def test_unknown_signal_raises(self):
        with pytest.raises(ValueError, match="Unknown signal"):
            resolve_signal_names("UNKNOWN")

    def test_empty_string(self):
        assert resolve_signal_names("") == []

    def test_case_insensitive_abbreviation(self):
        assert resolve_signal_names("pfs") == ["pattern_fragmentation"]


class TestApplySignalFilter:
    def test_default_tvs_is_report_only(self):
        cfg = DriftConfig()
        assert cfg.weights.temporal_volatility == 0.0

    def test_select_keeps_only_selected(self):
        cfg = DriftConfig()
        apply_signal_filter(cfg, select="PFS,AVS", ignore=None)
        assert cfg.weights.pattern_fragmentation > 0
        assert cfg.weights.architecture_violation > 0
        assert cfg.weights.mutant_duplicate == 0.0
        assert cfg.weights.temporal_volatility == 0.0

    def test_ignore_zeroes_ignored(self):
        cfg = DriftConfig()
        original_pfs = cfg.weights.pattern_fragmentation
        apply_signal_filter(cfg, select=None, ignore="TVS,DIA")
        assert cfg.weights.temporal_volatility == 0.0
        assert cfg.weights.doc_impl_drift == 0.0
        assert cfg.weights.pattern_fragmentation == original_pfs

    def test_select_then_ignore(self):
        cfg = DriftConfig()
        apply_signal_filter(cfg, select="PFS,AVS,MDS", ignore="AVS")
        assert cfg.weights.pattern_fragmentation > 0
        assert cfg.weights.architecture_violation == 0.0  # ignored after select
        assert cfg.weights.mutant_duplicate > 0

    def test_no_filter_is_noop(self):
        cfg = DriftConfig()
        original = cfg.weights.model_dump()
        apply_signal_filter(cfg, select=None, ignore=None)
        assert cfg.weights.model_dump() == original


# ---------------------------------------------------------------------------
# pyproject.toml config loading
# ---------------------------------------------------------------------------


class TestPyprojectToml:
    def test_load_from_pyproject(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent("""\
            [tool.drift]
            fail_on = "medium"

            [tool.drift.weights]
            pattern_fragmentation = 0.30
        """)
        )
        cfg = DriftConfig.load(tmp_path)
        assert cfg.fail_on == "medium"
        assert cfg.weights.pattern_fragmentation == 0.30

    def test_pyproject_without_drift_section_returns_defaults(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent("""\
            [tool.ruff]
            line-length = 88
        """)
        )
        cfg = DriftConfig.load(tmp_path)
        assert cfg.fail_on == "high"  # default

    def test_drift_yaml_takes_priority_over_pyproject(self, tmp_path: Path):
        (tmp_path / "drift.yaml").write_text("fail_on: critical\n")
        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent("""\
            [tool.drift]
            fail_on = "low"
        """)
        )
        cfg = DriftConfig.load(tmp_path)
        assert cfg.fail_on == "critical"  # YAML wins

    def test_drift_toml_standalone(self, tmp_path: Path):
        (tmp_path / "drift.toml").write_text(
            textwrap.dedent("""\
            fail_on = "low"

            [weights]
            pattern_fragmentation = 0.50
        """)
        )
        cfg = DriftConfig.load(tmp_path)
        assert cfg.fail_on == "low"
        assert cfg.weights.pattern_fragmentation == 0.50

    def test_drift_toml_priority_over_pyproject(self, tmp_path: Path):
        (tmp_path / "drift.toml").write_text('fail_on = "medium"\n')
        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent("""\
            [tool.drift]
            fail_on = "low"
        """)
        )
        cfg = DriftConfig.load(tmp_path)
        assert cfg.fail_on == "medium"  # drift.toml wins

    def test_load_from_pyproject_with_utf8_bom(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent("""\
            [tool.drift]
            fail_on = "medium"
            """),
            encoding="utf-8-sig",
        )

        cfg = DriftConfig.load(tmp_path)
        assert cfg.fail_on == "medium"


# ---------------------------------------------------------------------------
# GitHub annotation output format
# ---------------------------------------------------------------------------


class TestGitHubFormat:
    def test_findings_to_github_annotations(self):
        from drift.models import Finding, RepoAnalysis, Severity, SignalType

        finding = Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            rule_id="pfs_error_handling",
            severity=Severity.HIGH,
            score=0.75,
            impact=3,
            title="3 incompatible error handling variants",
            description="Multiple error handling patterns detected.",
            fix="Consolidate to one canonical pattern.",
            file_path=Path("src/app/service.py"),
            start_line=42,
            end_line=89,
        )
        analysis = RepoAnalysis(
            repo_path=Path("."),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.5,
            module_scores=[],
            findings=[finding],
        )

        from drift.output.github_format import findings_to_github_annotations

        output = findings_to_github_annotations(analysis)
        assert "::error" in output
        assert "file=src/app/service.py" in output
        assert "line=42" in output
        assert "endLine=89" in output
        assert "pattern_fragmentation" in output
        assert "Fix: Consolidate" in output

    def test_severity_mapping(self):
        from drift.models import Finding, RepoAnalysis, Severity, SignalType
        from drift.output.github_format import findings_to_github_annotations

        severities = {
            Severity.CRITICAL: "::error",
            Severity.HIGH: "::error",
            Severity.MEDIUM: "::warning",
            Severity.LOW: "::notice",
            Severity.INFO: "::notice",
        }
        for sev, expected_level in severities.items():
            finding = Finding(
                signal_type=SignalType.PATTERN_FRAGMENTATION,
                rule_id="test",
                severity=sev,
                score=0.5,
                impact=1,
                title="test",
                description="test",
                fix="test",
                file_path=Path("test.py"),
                start_line=1,
                end_line=1,
            )
            analysis = RepoAnalysis(
                repo_path=Path("."),
                analyzed_at=datetime.datetime.now(tz=datetime.UTC),
                drift_score=0.5,
                module_scores=[],
                findings=[finding],
            )
            output = findings_to_github_annotations(analysis)
            assert output.startswith(expected_level), f"Expected {expected_level} for {sev}"

    def test_empty_findings(self):
        from drift.models import RepoAnalysis
        from drift.output.github_format import findings_to_github_annotations

        analysis = RepoAnalysis(
            repo_path=Path("."),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.0,
            module_scores=[],
            findings=[],
        )
        output = findings_to_github_annotations(analysis)
        assert output == ""

    def test_newlines_in_description_and_fix_are_encoded(self):
        """Newlines in description/fix must be %0A-encoded (issue #388)."""
        from drift.models import Finding, RepoAnalysis, Severity, SignalType
        from drift.output.github_format import findings_to_github_annotations

        finding = Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            rule_id="test",
            severity=Severity.HIGH,
            score=0.5,
            impact=1,
            title="multi-line test",
            description="First sentence.\nSecond sentence.",
            fix="Fix line one.\nFix line two.",
            file_path=Path("src/foo.py"),
            start_line=1,
            end_line=1,
        )
        analysis = RepoAnalysis(
            repo_path=Path("."),
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.5,
            module_scores=[],
            findings=[finding],
        )
        output = findings_to_github_annotations(analysis)
        # Must be a single line per annotation
        assert "\n" not in output
        # Newlines must be percent-encoded
        assert "%0A" in output
        assert "First sentence.%0ASecond sentence." in output
        assert "Fix line one.%0AFix line two." in output


# ---------------------------------------------------------------------------
# CLI --output-format alias
# ---------------------------------------------------------------------------


class TestOutputFormatAlias:
    def test_format_and_output_format_both_accepted(self):
        """Both --format and --output-format should be valid flags."""
        from drift.commands.check import check

        runner = CliRunner()
        # --format should not raise "no such option"
        result = runner.invoke(check, ["--format", "json", "--help"], catch_exceptions=False)
        assert result.exit_code == 0

        # --output-format should not raise "no such option"
        result = runner.invoke(check, ["--output-format", "json", "--help"], catch_exceptions=False)
        assert result.exit_code == 0

    def test_github_format_in_choices(self):
        """github should be a valid output format choice."""
        from drift.commands.check import check

        runner = CliRunner()
        result = runner.invoke(check, ["--output-format", "github", "--help"])
        assert result.exit_code == 0

    def test_csv_format_in_choices(self):
        """csv should be a valid output format choice."""
        from drift.commands.check import check

        runner = CliRunner()
        result = runner.invoke(check, ["--output-format", "csv", "--help"])
        assert result.exit_code == 0

    def test_analyze_format_alias(self):
        """analyze command should also accept --output-format."""
        from drift.commands.analyze import analyze

        runner = CliRunner()
        result = runner.invoke(
            analyze, ["--output-format", "json", "--help"], catch_exceptions=False
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# --select filters findings in check output (#87)
# ---------------------------------------------------------------------------


class TestCheckSelectFilter:
    def test_select_filters_findings_to_selected_signal(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """#87: --select PFS should only emit PFS findings."""
        import json

        from drift.cli import main
        from drift.models import Finding, RepoAnalysis, Severity, SignalType

        repo = tmp_path / "repo"
        repo.mkdir(parents=True, exist_ok=True)

        pfs_finding = Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.HIGH,
            score=0.8,
            title="PFS finding",
            description="PFS",
            file_path=Path("src/a.py"),
            start_line=10,
            fix="Fix PFS.",
        )
        avs_finding = Finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            severity=Severity.MEDIUM,
            score=0.5,
            title="AVS finding",
            description="AVS",
            file_path=Path("src/b.py"),
            start_line=20,
            fix="Fix AVS.",
        )

        def _fake_analyze_diff(*_args, **_kwargs) -> RepoAnalysis:
            return RepoAnalysis(
                repo_path=repo,
                analyzed_at=datetime.datetime.now(datetime.UTC),
                drift_score=0.7,
                findings=[pfs_finding, avs_finding],
            )

        monkeypatch.setattr("drift.analyzer.analyze_diff", _fake_analyze_diff)

        out_file = tmp_path / "result.json"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "check",
                "--repo",
                str(repo),
                "--select",
                "PFS",
                "--json",
                "--compact",
                "-o",
                str(out_file),
                "--exit-zero",
            ],
        )
        assert result.exit_code == 0

        payload = json.loads(out_file.read_text(encoding="utf-8"))
        signals = {f["signal"] for f in payload["findings_compact"]}
        assert signals == {"pattern_fragmentation"}
        assert len(payload["findings_compact"]) == 1

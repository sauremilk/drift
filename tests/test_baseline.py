"""Tests for drift baseline — save, load, diff, and CLI commands."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from drift.baseline import baseline_diff, finding_fingerprint, load_baseline, save_baseline
from drift.models import Finding, RepoAnalysis, Severity, SignalType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(
    signal: SignalType = SignalType.PATTERN_FRAGMENTATION,
    severity: Severity = Severity.MEDIUM,
    file_path: str = "src/foo.py",
    start_line: int = 10,
    title: str = "Test finding",
    **kwargs,
) -> Finding:
    return Finding(
        signal_type=signal,
        severity=severity,
        score=0.5,
        title=title,
        description="A test finding.",
        file_path=Path(file_path),
        start_line=start_line,
        end_line=kwargs.get("end_line", start_line + 5),
        fix="Refactor the code.",
    )


def _make_analysis(findings: list[Finding] | None = None) -> RepoAnalysis:
    import datetime

    return RepoAnalysis(
        repo_path=Path("."),
        analyzed_at=datetime.datetime.now(datetime.UTC),
        drift_score=0.35,
        findings=findings or [],
    )


# ===========================================================================
# Unit tests: finding_fingerprint
# ===========================================================================


class TestFindingFingerprint:
    def test_deterministic(self) -> None:
        f = _make_finding()
        assert finding_fingerprint(f) == finding_fingerprint(f)

    def test_changes_with_signal(self) -> None:
        f1 = _make_finding(signal=SignalType.PATTERN_FRAGMENTATION)
        f2 = _make_finding(signal=SignalType.MUTANT_DUPLICATE)
        assert finding_fingerprint(f1) != finding_fingerprint(f2)

    def test_changes_with_file(self) -> None:
        f1 = _make_finding(file_path="a.py")
        f2 = _make_finding(file_path="b.py")
        assert finding_fingerprint(f1) != finding_fingerprint(f2)

    def test_changes_with_line(self) -> None:
        f1 = _make_finding(start_line=10)
        f2 = _make_finding(start_line=20)
        assert finding_fingerprint(f1) != finding_fingerprint(f2)

    def test_changes_with_title(self) -> None:
        f1 = _make_finding(title="X")
        f2 = _make_finding(title="Y")
        assert finding_fingerprint(f1) != finding_fingerprint(f2)

    def test_none_file_path(self) -> None:
        f = _make_finding()
        f.file_path = None
        fp = finding_fingerprint(f)
        assert isinstance(fp, str) and len(fp) == 16

    def test_hex_string_format(self) -> None:
        f = _make_finding()
        fp = finding_fingerprint(f)
        assert len(fp) == 16
        int(fp, 16)  # must be valid hex


# ===========================================================================
# Unit tests: save_baseline / load_baseline
# ===========================================================================


class TestBaselineIO:
    def test_roundtrip(self, tmp_path: Path) -> None:
        findings = [
            _make_finding(title="A"),
            _make_finding(title="B", file_path="src/bar.py"),
        ]
        analysis = _make_analysis(findings)
        bl_path = tmp_path / ".drift-baseline.json"

        save_baseline(analysis, bl_path)
        assert bl_path.exists()

        fps = load_baseline(bl_path)
        assert len(fps) == 2
        assert finding_fingerprint(findings[0]) in fps
        assert finding_fingerprint(findings[1]) in fps

    def test_file_structure(self, tmp_path: Path) -> None:
        findings = [_make_finding()]
        analysis = _make_analysis(findings)
        bl_path = tmp_path / "baseline.json"

        save_baseline(analysis, bl_path)
        data = json.loads(bl_path.read_text())

        assert "baseline_version" in data
        assert "drift_version" in data
        assert "created_at" in data
        assert data["finding_count"] == 1
        assert len(data["findings"]) == 1

        entry = data["findings"][0]
        assert "fingerprint" in entry
        assert entry["signal"] == "pattern_fragmentation"
        assert entry["file"] == "src/foo.py"

    def test_empty_baseline(self, tmp_path: Path) -> None:
        analysis = _make_analysis([])
        bl_path = tmp_path / "empty.json"

        save_baseline(analysis, bl_path)
        fps = load_baseline(bl_path)
        assert fps == set()

    def test_invalid_file_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text('{"not": "a baseline"}')

        with pytest.raises(ValueError, match="Invalid baseline"):
            load_baseline(bad)


# ===========================================================================
# Unit tests: baseline_diff
# ===========================================================================


class TestBaselineDiff:
    def test_all_new(self) -> None:
        findings = [_make_finding(title="A"), _make_finding(title="B")]
        new, known = baseline_diff(findings, set())
        assert len(new) == 2
        assert len(known) == 0

    def test_all_known(self) -> None:
        findings = [_make_finding(title="A"), _make_finding(title="B")]
        fps = {finding_fingerprint(f) for f in findings}
        new, known = baseline_diff(findings, fps)
        assert len(new) == 0
        assert len(known) == 2

    def test_mixed(self) -> None:
        f_old = _make_finding(title="Old")
        f_new = _make_finding(title="New")
        baseline_fps = {finding_fingerprint(f_old)}

        new, known = baseline_diff([f_old, f_new], baseline_fps)
        assert len(new) == 1
        assert len(known) == 1
        assert new[0].title == "New"
        assert known[0].title == "Old"

    def test_empty_findings(self) -> None:
        new, known = baseline_diff([], {"abc123"})
        assert new == []
        assert known == []


# ===========================================================================
# CLI tests: drift baseline save / diff
# ===========================================================================


class TestBaselineCLI:
    def test_help(self) -> None:
        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["baseline", "--help"])
        assert result.exit_code == 0
        assert "save" in result.output
        assert "diff" in result.output

    def test_save_help(self) -> None:
        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["baseline", "save", "--help"])
        assert result.exit_code == 0
        assert "--repo" in result.output
        assert "--output" in result.output

    def test_diff_help(self) -> None:
        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["baseline", "diff", "--help"])
        assert result.exit_code == 0
        assert "--baseline-file" in result.output
        assert "--format" in result.output


# ===========================================================================
# CLI tests: --baseline flag on analyze / check
# ===========================================================================


class TestBaselineFlagOnAnalyze:
    def test_analyze_has_baseline_option(self) -> None:
        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "--baseline" in result.output

    def test_check_has_baseline_option(self) -> None:
        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["check", "--help"])
        assert result.exit_code == 0
        assert "--baseline" in result.output

    def test_analyze_baseline_recomputes_summary(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        from drift.cli import main

        repo = tmp_path / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        baseline_file = tmp_path / "baseline.json"

        finding = _make_finding(
            signal=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.HIGH,
            title="Existing",
        )
        save_baseline(_make_analysis([finding]), baseline_file)

        def _fake_analyze_repo(*_args, **_kwargs) -> RepoAnalysis:
            return RepoAnalysis(
                repo_path=repo,
                analyzed_at=datetime.datetime.now(datetime.UTC),
                drift_score=0.7,
                findings=[finding],
            )

        monkeypatch.setattr("drift.analyzer.analyze_repo", _fake_analyze_repo)

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "analyze",
                "--repo",
                str(repo),
                "--baseline",
                str(baseline_file),
                "-q",
                "--exit-zero",
            ],
        )
        assert result.exit_code == 0
        assert "score: 0.00" in result.output
        assert "severity: INFO" in result.output
        assert "findings: 0" in result.output

    def test_check_baseline_recomputes_summary(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        from drift.cli import main

        repo = tmp_path / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        baseline_file = tmp_path / "baseline.json"

        finding = _make_finding(
            signal=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.HIGH,
            title="Existing",
        )
        save_baseline(_make_analysis([finding]), baseline_file)

        def _fake_analyze_diff(*_args, **_kwargs) -> RepoAnalysis:
            return RepoAnalysis(
                repo_path=repo,
                analyzed_at=datetime.datetime.now(datetime.UTC),
                drift_score=0.7,
                findings=[finding],
            )

        monkeypatch.setattr("drift.analyzer.analyze_diff", _fake_analyze_diff)

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "check",
                "--repo",
                str(repo),
                "--baseline",
                str(baseline_file),
                "-q",
                "--exit-zero",
            ],
        )
        assert result.exit_code == 0
        assert "score: 0.00" in result.output
        assert "severity: INFO" in result.output
        assert "findings: 0" in result.output

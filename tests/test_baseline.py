"""Tests for drift baseline — save, load, diff, and CLI commands."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from drift.baseline import (
    baseline_diff,
    finding_fingerprint,
    finding_fingerprint_v1,
    finding_fingerprint_v2,
    load_baseline,
    save_baseline,
    stable_title,
)
from drift.models import Finding, LogicalLocation, RepoAnalysis, Severity, SignalType

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
        """v2 contract: pure line-shift without symbol/title change must NOT
        change the fingerprint (see ADR-082). v1 remains line-sensitive."""
        f1 = _make_finding(start_line=10)
        f2 = _make_finding(start_line=20)
        # v2 (canonical) must be stable under pure line-shift.
        assert finding_fingerprint(f1) == finding_fingerprint(f2)
        # v1 (legacy) remains line-sensitive by design.
        assert finding_fingerprint_v1(f1) != finding_fingerprint_v1(f2)

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
# Unit tests: fingerprint v2 stability contract (ADR-082)
# ===========================================================================


class TestFingerprintV2Stability:
    """v2 fingerprint must be stable across line-shifts and metric-title
    changes, and must remain sensitive to genuine symbol renames."""

    def _with_symbol(
        self,
        symbol: str,
        start_line: int = 10,
        title: str = "Unexplained complexity: main",
    ) -> Finding:
        f = _make_finding(start_line=start_line, title=title)
        f.symbol = symbol
        f.logical_location = LogicalLocation(
            fully_qualified_name=f"mod.{symbol}",
            name=symbol,
            kind="function",
        )
        return f

    def test_stable_across_line_shift(self) -> None:
        """Pure line-shift within the same symbol must not shift v2."""
        f1 = self._with_symbol("main", start_line=10)
        f2 = self._with_symbol("main", start_line=120)
        assert finding_fingerprint_v2(f1) == finding_fingerprint_v2(f2)

    def test_stable_across_metric_title_change(self) -> None:
        """Changing a numeric metric in the title must not shift v2."""
        f1 = self._with_symbol("main", title="return_pattern: 2 variants in scripts/")
        f2 = self._with_symbol("main", title="return_pattern: 5 variants in scripts/")
        assert finding_fingerprint_v2(f1) == finding_fingerprint_v2(f2)

    def test_stable_across_trailing_refs(self) -> None:
        """Trailing ``(file:line)`` references must be stripped before hashing."""
        f1 = self._with_symbol("main", title="deviation (scripts/foo.py:87)")
        f2 = self._with_symbol("main", title="deviation (scripts/foo.py:112)")
        assert finding_fingerprint_v2(f1) == finding_fingerprint_v2(f2)

    def test_detects_genuine_rename(self) -> None:
        """Different symbol identity must produce a different v2 fingerprint."""
        f1 = self._with_symbol("login")
        f2 = self._with_symbol("signin")
        assert finding_fingerprint_v2(f1) != finding_fingerprint_v2(f2)

    def test_detects_file_move(self) -> None:
        """Moving a finding to a different file must shift v2."""
        f1 = self._with_symbol("main")
        f1.file_path = Path("a/foo.py")
        f2 = self._with_symbol("main")
        f2.file_path = Path("b/foo.py")
        assert finding_fingerprint_v2(f1) != finding_fingerprint_v2(f2)

    def test_detects_signal_change(self) -> None:
        """Different signal_type must shift v2 even if everything else matches."""
        f1 = self._with_symbol("main")
        f1.signal_type = SignalType.PATTERN_FRAGMENTATION
        f2 = self._with_symbol("main")
        f2.signal_type = SignalType.MUTANT_DUPLICATE
        assert finding_fingerprint_v2(f1) != finding_fingerprint_v2(f2)

    def test_falls_back_to_symbol_when_no_logical_location(self) -> None:
        """Findings without logical_location but with symbol still get a
        stable, symbol-bound fingerprint."""
        f1 = _make_finding(start_line=10)
        f1.symbol = "main"
        f2 = _make_finding(start_line=120)
        f2.symbol = "main"
        assert finding_fingerprint_v2(f1) == finding_fingerprint_v2(f2)

    def test_falls_back_to_file_when_no_symbol(self) -> None:
        """Findings without any symbol identity hash on (signal, file, title)
        only — line-independent but not symbol-scoped."""
        f1 = _make_finding(start_line=10, title="Happy-path-only test suite in tests/")
        f2 = _make_finding(start_line=500, title="Happy-path-only test suite in tests/")
        assert finding_fingerprint_v2(f1) == finding_fingerprint_v2(f2)


class TestStableTitle:
    """Unit tests for the title-normalisation helper."""

    def test_strips_leading_metric(self) -> None:
        assert stable_title("2 variants in scripts/") == "<N> variants in scripts/"

    def test_strips_multiple_metrics(self) -> None:
        assert (
            stable_title("error_handling: 5 variants (4 unique)")
            == "error_handling: <N> variants (<N> unique)"
        )

    def test_strips_trailing_file_line_refs(self) -> None:
        assert (
            stable_title("Deviation (scripts/foo.py:87)")
            == "Deviation"
        )

    def test_preserves_stable_text(self) -> None:
        assert stable_title("Unexplained complexity: main") == "Unexplained complexity: main"

    def test_empty_and_none_safe(self) -> None:
        assert stable_title("") == ""


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

    def test_version_mismatch_emits_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """load_baseline() should warn when stored drift_version != running version."""
        import logging

        findings = [_make_finding(title="A")]
        analysis = _make_analysis(findings)
        bl_path = tmp_path / "baseline.json"

        save_baseline(analysis, bl_path)

        # Tamper stored version to simulate a version upgrade.
        data = json.loads(bl_path.read_text())
        data["drift_version"] = "0.0.0-old"
        bl_path.write_text(json.dumps(data), encoding="utf-8")

        with caplog.at_level(logging.WARNING, logger="drift.baseline"):
            fps = load_baseline(bl_path)

        # Fingerprints are still returned.
        assert len(fps) == 1
        # A warning must have been emitted.
        assert any(
            "0.0.0-old" in record.message and record.name == "drift.baseline"
            for record in caplog.records
        )

    def test_same_version_no_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """load_baseline() should not warn when versions match."""
        import logging

        findings = [_make_finding(title="A")]
        analysis = _make_analysis(findings)
        bl_path = tmp_path / "baseline.json"

        save_baseline(analysis, bl_path)

        with caplog.at_level(logging.WARNING, logger="drift.baseline"):
            load_baseline(bl_path)

        assert not any(r.name == "drift.baseline" for r in caplog.records)

    def test_missing_version_field_no_error(self, tmp_path: Path) -> None:
        """load_baseline() must not crash when drift_version field is absent (legacy files)."""
        findings = [_make_finding(title="A")]
        analysis = _make_analysis(findings)
        bl_path = tmp_path / "baseline.json"

        save_baseline(analysis, bl_path)
        data = json.loads(bl_path.read_text())
        del data["drift_version"]
        bl_path.write_text(json.dumps(data), encoding="utf-8")

        fps = load_baseline(bl_path)
        assert len(fps) == 1

    def test_save_writes_v2_schema_with_v1_alias(self, tmp_path: Path) -> None:
        """Saved entries must contain both v2 'fingerprint' and 'fingerprint_v1'
        alias (see ADR-082 migration window)."""
        findings = [_make_finding(title="A")]
        analysis = _make_analysis(findings)
        bl_path = tmp_path / "baseline.json"

        save_baseline(analysis, bl_path)
        data = json.loads(bl_path.read_text())

        assert data["baseline_version"] == 2
        entry = data["findings"][0]
        assert entry["fingerprint"] == finding_fingerprint_v2(findings[0])
        assert entry["fingerprint_v1"] == finding_fingerprint_v1(findings[0])

    def test_v1_schema_baseline_still_loads(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Legacy v1-schema baseline files must still load, emit a schema
        upgrade warning, and remain matchable via baseline_diff."""
        import logging

        findings = [_make_finding(title="A")]
        v1_baseline = {
            "baseline_version": 1,
            "drift_version": "1.0.0-legacy",
            "created_at": "2025-01-01T00:00:00+00:00",
            "drift_score": 0.1,
            "finding_count": 1,
            "findings": [
                {
                    "fingerprint": finding_fingerprint_v1(findings[0]),
                    "signal": findings[0].signal_type,
                    "severity": findings[0].severity.value,
                    "file": findings[0].file_path.as_posix(),
                    "start_line": findings[0].start_line,
                    "title": findings[0].title,
                }
            ],
        }
        bl_path = tmp_path / "baseline.json"
        bl_path.write_text(json.dumps(v1_baseline), encoding="utf-8")

        with caplog.at_level(logging.WARNING, logger="drift.baseline"):
            fps = load_baseline(bl_path)

        # The returned set contains the v1 fingerprint as stored.
        assert fps == {finding_fingerprint_v1(findings[0])}

        # baseline_diff must still recognise the finding as known because
        # it checks BOTH v2 and v1 against the baseline set.
        new, known = baseline_diff(findings, fps)
        assert new == []
        assert len(known) == 1

        # A schema-upgrade warning must have been emitted.
        assert any(
            "Baseline schema v1 is older than current v2" in r.message
            for r in caplog.records
        )


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

    def test_diff_missing_baseline_suggests_save_command(
        self,
        tmp_path: Path,
    ) -> None:
        from drift.cli import main

        runner = CliRunner()
        repo = tmp_path / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        baseline_file = tmp_path / "missing-baseline.json"

        result = runner.invoke(
            main,
            [
                "baseline",
                "diff",
                "--repo",
                str(repo),
                "--baseline-file",
                str(baseline_file),
            ],
        )

        assert result.exit_code == 1
        assert "Baseline not found" in result.output
        normalized = result.output.replace("\n", " ")
        assert "drift baseline save --output" in normalized
        assert baseline_file.name in normalized


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

    def test_check_baseline_updates_suppressed_count(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """#89: suppressed_count must reflect baseline-filtered findings."""
        from drift.cli import main

        repo = tmp_path / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        baseline_file = tmp_path / "baseline.json"

        known_finding = _make_finding(
            signal=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.HIGH,
            title="Known",
        )
        new_finding = _make_finding(
            signal=SignalType.MUTANT_DUPLICATE,
            severity=Severity.MEDIUM,
            title="New",
            file_path="src/bar.py",
        )
        save_baseline(_make_analysis([known_finding]), baseline_file)

        def _fake_analyze_diff(*_args, **_kwargs) -> RepoAnalysis:
            return RepoAnalysis(
                repo_path=repo,
                analyzed_at=datetime.datetime.now(datetime.UTC),
                drift_score=0.7,
                findings=[known_finding, new_finding],
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
                "--baseline",
                str(baseline_file),
                "--json",
                "--compact",
                "-o",
                str(out_file),
                "--exit-zero",
            ],
        )
        assert result.exit_code == 0

        import json as _json

        payload = _json.loads(out_file.read_text(encoding="utf-8"))
        assert payload["suppressed_count"] == 1
        assert len(payload["findings_compact"]) == 1

    def test_check_baseline_json_includes_baseline_counts(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """#156: JSON output must include new_findings_count and baseline_matched_count."""
        from drift.cli import main

        repo = tmp_path / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        baseline_file = tmp_path / "baseline.json"

        known_finding = _make_finding(
            signal=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.HIGH,
            title="Known",
        )
        new_finding = _make_finding(
            signal=SignalType.MUTANT_DUPLICATE,
            severity=Severity.MEDIUM,
            title="New",
            file_path="src/bar.py",
        )
        save_baseline(_make_analysis([known_finding]), baseline_file)

        def _fake_analyze_diff(*_args, **_kwargs) -> RepoAnalysis:
            return RepoAnalysis(
                repo_path=repo,
                analyzed_at=datetime.datetime.now(datetime.UTC),
                drift_score=0.7,
                findings=[known_finding, new_finding],
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
                "--baseline",
                str(baseline_file),
                "--json",
                "--compact",
                "-o",
                str(out_file),
                "--exit-zero",
            ],
        )
        assert result.exit_code == 0

        import json as _json

        payload = _json.loads(out_file.read_text(encoding="utf-8"))
        assert payload["baseline"]["applied"] is True
        assert payload["baseline"]["new_findings_count"] == 1
        assert payload["baseline"]["baseline_matched_count"] == 1


# ===========================================================================
# Tests for Issue #413: atomic save_baseline() and corrupt-file handling
# ===========================================================================


class TestAtomicSaveBaseline:
    def test_save_baseline_creates_file(self, tmp_path: Path) -> None:
        """save_baseline() must produce a valid, loadable file."""
        analysis = _make_analysis([_make_finding()])
        bl_path = tmp_path / "bl.json"

        save_baseline(analysis, bl_path)

        assert bl_path.exists()
        fps = load_baseline(bl_path)
        assert len(fps) == 1

    def test_save_baseline_no_temp_file_left_on_success(self, tmp_path: Path) -> None:
        """After a successful save, no *.json temp file must remain beside the baseline."""
        analysis = _make_analysis([_make_finding()])
        bl_path = tmp_path / "bl.json"

        save_baseline(analysis, bl_path)

        leftover = [f for f in tmp_path.iterdir() if f != bl_path]
        assert leftover == [], f"Unexpected temp files: {leftover}"

    def test_save_baseline_atomic_replaces_existing(self, tmp_path: Path) -> None:
        """A second save must atomically replace the first without leaving partial data."""
        analysis1 = _make_analysis([_make_finding(title="First")])
        analysis2 = _make_analysis([_make_finding(title="Second"), _make_finding(title="Third")])
        bl_path = tmp_path / "bl.json"

        save_baseline(analysis1, bl_path)
        save_baseline(analysis2, bl_path)

        fps = load_baseline(bl_path)
        assert len(fps) == 2


class TestCorruptBaselineCallers:
    """Callers must emit a friendly error instead of a bare traceback on corrupt baseline."""

    def _write_corrupt(self, path: Path) -> None:
        path.write_text("{ this is not json", encoding="utf-8")

    def test_ci_corrupt_baseline_exits_with_message(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """drift ci --baseline on a corrupt file must exit 1 with a friendly message."""
        from click.testing import CliRunner

        from drift.cli import main

        repo = tmp_path / "repo"
        repo.mkdir()
        bl = tmp_path / "bad.json"
        self._write_corrupt(bl)

        def _fake_analyze(*_a, **_kw):
            return _make_analysis([])

        monkeypatch.setattr("drift.analyzer.analyze_repo", _fake_analyze)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["ci", "--repo", str(repo), "--baseline", str(bl), "--exit-zero"],
            catch_exceptions=False,
        )
        assert result.exit_code == 1
        assert "corrupt" in result.output.lower()
        assert "drift baseline save" in result.output

    def test_shared_apply_baseline_filtering_corrupt(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """apply_baseline_filtering() must raise SystemExit(1) on corrupt baseline."""
        from drift.commands._shared import apply_baseline_filtering
        from drift.config import DriftConfig

        bl = tmp_path / "bad.json"
        self._write_corrupt(bl)
        analysis = _make_analysis([_make_finding()])
        cfg = DriftConfig()

        with pytest.raises(SystemExit) as exc_info:
            apply_baseline_filtering(analysis, cfg, bl)
        assert exc_info.value.code == 1

    def test_baseline_diff_command_corrupt(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """drift baseline diff on a corrupt file must exit 1 with a friendly message."""
        from click.testing import CliRunner

        from drift.cli import main

        repo = tmp_path / "repo"
        repo.mkdir()
        bl = tmp_path / "bad.json"
        self._write_corrupt(bl)

        def _fake_analyze(*_a, **_kw):
            return _make_analysis([])

        monkeypatch.setattr("drift.analyzer.analyze_repo", _fake_analyze)

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["baseline", "diff", "--repo", str(repo), "--baseline-file", str(bl)],
            catch_exceptions=False,
        )
        assert result.exit_code == 1
        assert "corrupt" in result.output.lower()

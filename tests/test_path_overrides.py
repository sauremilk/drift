"""Tests for per-path configuration overrides."""

from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig, PathOverride, SignalWeights
from drift.models import Finding, Severity, SignalType
from drift.scoring.engine import apply_path_overrides, resolve_path_override

# ── resolve_path_override ───────────────────────────────────────────────────


class TestResolvePathOverride:
    def test_no_overrides_returns_none(self) -> None:
        assert resolve_path_override(Path("src/foo.py"), {}) is None

    def test_none_path_returns_none(self) -> None:
        overrides = {"src/**": PathOverride()}
        assert resolve_path_override(None, overrides) is None

    def test_matching_glob(self) -> None:
        override = PathOverride(exclude_signals=["pattern_fragmentation"])
        overrides = {"tests/**": override}
        result = resolve_path_override(Path("tests/test_foo.py"), overrides)
        assert result is override

    def test_no_match(self) -> None:
        overrides = {"tests/**": PathOverride()}
        assert resolve_path_override(Path("src/foo.py"), overrides) is None

    def test_most_specific_wins(self) -> None:
        broad = PathOverride(exclude_signals=["a"])
        specific = PathOverride(exclude_signals=["b"])
        overrides = {
            "src/**": broad,
            "src/deep/nested/**": specific,
        }
        result = resolve_path_override(Path("src/deep/nested/foo.py"), overrides)
        assert result is specific

    def test_exact_directory_match(self) -> None:
        override = PathOverride(severity_gate="critical")
        overrides = {"legacy/*": override}
        result = resolve_path_override(Path("legacy/old.py"), overrides)
        assert result is override


# ── apply_path_overrides ────────────────────────────────────────────────────


def _make_finding(
    signal: SignalType = SignalType.PATTERN_FRAGMENTATION,
    file_path: str = "src/foo.py",
    score: float = 0.7,
) -> Finding:
    return Finding(
        signal_type=signal,
        severity=Severity.HIGH,
        score=score,
        title="test",
        description="d",
        file_path=Path(file_path),
    )


class TestApplyPathOverrides:
    def test_no_overrides_returns_all(self) -> None:
        findings = [_make_finding(), _make_finding(file_path="src/bar.py")]
        result = apply_path_overrides(findings, {}, SignalWeights())
        assert len(result) == 2

    def test_exclude_signal_removes_finding(self) -> None:
        findings = [
            _make_finding(file_path="tests/test_a.py"),
            _make_finding(file_path="src/main.py"),
        ]
        overrides = {"tests/**": PathOverride(exclude_signals=["pattern_fragmentation"])}
        result = apply_path_overrides(findings, overrides, SignalWeights())
        assert len(result) == 1
        assert result[0].file_path == Path("src/main.py")

    def test_non_matching_signal_kept(self) -> None:
        findings = [
            _make_finding(
                signal=SignalType.ARCHITECTURE_VIOLATION,
                file_path="tests/test_a.py",
            ),
        ]
        overrides = {"tests/**": PathOverride(exclude_signals=["pattern_fragmentation"])}
        result = apply_path_overrides(findings, overrides, SignalWeights())
        assert len(result) == 1

    def test_custom_weights_recompute_impact(self) -> None:
        f = _make_finding(file_path="legacy/old.py", score=0.8)
        f.impact = 999.0  # marker
        low_weights = SignalWeights(pattern_fragmentation=0.01)
        overrides = {"legacy/**": PathOverride(weights=low_weights)}
        result = apply_path_overrides([f], overrides, SignalWeights())
        assert len(result) == 1
        assert result[0].impact < 1.0  # much lower than the marker

    def test_overlapping_globs_specific_wins(self) -> None:
        f = _make_finding(file_path="tests/unit/test_foo.py")
        overrides = {
            "tests/**": PathOverride(exclude_signals=["pattern_fragmentation"]),
            "tests/unit/**": PathOverride(exclude_signals=[]),  # more specific, no exclusions
        }
        result = apply_path_overrides([f], overrides, SignalWeights())
        assert len(result) == 1  # unit override keeps it


# ── Config loading ──────────────────────────────────────────────────────────


class TestPathOverrideConfig:
    def test_path_override_loads_from_yaml(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "drift.yaml"
        cfg_file.write_text(
            "path_overrides:\n"
            '  "tests/**":\n'
            "    exclude_signals:\n"
            "      - pattern_fragmentation\n"
            '  "legacy/**":\n'
            "    severity_gate: critical\n",
            encoding="utf-8",
        )
        cfg = DriftConfig.load(tmp_path)
        assert "tests/**" in cfg.path_overrides
        assert "legacy/**" in cfg.path_overrides
        assert cfg.path_overrides["tests/**"].exclude_signals == ["pattern_fragmentation"]
        assert cfg.path_overrides["legacy/**"].severity_gate == "critical"

    def test_empty_path_overrides_is_default(self, tmp_path: Path) -> None:
        cfg = DriftConfig.load(tmp_path)
        assert cfg.path_overrides == {}

    def test_path_override_with_custom_weights(self, tmp_path: Path) -> None:
        cfg_file = tmp_path / "drift.yaml"
        cfg_file.write_text(
            "path_overrides:\n"
            '  "scripts/**":\n'
            "    weights:\n"
            "      pattern_fragmentation: 0.01\n"
            "      architecture_violation: 0.01\n",
            encoding="utf-8",
        )
        cfg = DriftConfig.load(tmp_path)
        override = cfg.path_overrides["scripts/**"]
        assert override.weights is not None
        assert override.weights.pattern_fragmentation == 0.01


# ── Config validate with path overrides ────────────────────────────────────


class TestConfigValidatePathOverrides:
    def test_unknown_signal_in_exclude_warns(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        cfg_file = tmp_path / "drift.yaml"
        cfg_file.write_text(
            'path_overrides:\n  "tests/**":\n    exclude_signals:\n      - nonexistent_signal\n',
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(main, ["config", "validate", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert "unknown signal" in result.output.lower() or "nonexistent_signal" in result.output

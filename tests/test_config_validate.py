"""Tests for ``drift config validate`` and ``drift config show``."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from drift.cli import main


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def valid_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "drift.yaml"
    cfg.write_text(
        "weights:\n  pattern_fragmentation: 0.16\n  architecture_violation: 0.16\n"
        "fail_on: none\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def invalid_config(tmp_path: Path) -> Path:
    # Use an unknown top-level key rather than an unknown weight key,
    # because the Plugin API now accepts unknown weight keys as plugin weights.
    cfg = tmp_path / "drift.yaml"
    cfg.write_text("totally_invalid_top_level_key: true\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def extreme_weights_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "drift.yaml"
    cfg.write_text(
        "weights:\n  pattern_fragmentation: 99.0\n  architecture_violation: 0.01\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def negative_weight_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "drift.yaml"
    cfg.write_text(
        "weights:\n  pattern_fragmentation: -0.5\n",
        encoding="utf-8",
    )
    return tmp_path


# ── validate ────────────────────────────────────────────────────────────────


class TestConfigValidate:
    def test_valid_config_passes(self, runner: CliRunner, valid_config: Path) -> None:
        result = runner.invoke(main, ["config", "validate", "--repo", str(valid_config)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower() or "✓" in result.output

    def test_no_config_falls_to_defaults(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["config", "validate", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert "default" in result.output.lower()

    def test_invalid_config_exits_1(self, runner: CliRunner, invalid_config: Path) -> None:
        result = runner.invoke(main, ["config", "validate", "--repo", str(invalid_config)])
        assert result.exit_code == 1
        assert "invalid" in result.output.lower() or "✗" in result.output

    def test_invalid_config_shows_error_code(self, runner: CliRunner, invalid_config: Path) -> None:
        result = runner.invoke(main, ["config", "validate", "--repo", str(invalid_config)])
        assert result.exit_code == 1
        assert "DRIFT-1001" in result.output

    def test_invalid_config_shows_yaml_context(self, runner: CliRunner, tmp_path: Path) -> None:
        cfg = tmp_path / "drift.yaml"
        cfg.write_text(
            "weights:\n  pattern_fragmentation: 0.16\n"
            "  architecture_violation: not_a_number\n",
            encoding="utf-8",
        )
        result = runner.invoke(main, ["config", "validate", "--repo", str(tmp_path)])
        assert result.exit_code == 1
        # Should show YAML context with line numbers
        assert "│" in result.output

    def test_extreme_weights_warn(self, runner: CliRunner, extreme_weights_config: Path) -> None:
        result = runner.invoke(
            main, ["config", "validate", "--repo", str(extreme_weights_config)]
        )
        assert result.exit_code == 0
        assert "warning" in result.output.lower() or "⚠" in result.output

    def test_negative_weight_warn(self, runner: CliRunner, negative_weight_config: Path) -> None:
        result = runner.invoke(
            main, ["config", "validate", "--repo", str(negative_weight_config)]
        )
        assert result.exit_code == 0
        assert "negative" in result.output.lower()

    def test_explicit_config_path(self, runner: CliRunner, valid_config: Path) -> None:
        cfg_file = valid_config / "drift.yaml"
        result = runner.invoke(
            main,
            ["config", "validate", "--repo", str(valid_config), "--config", str(cfg_file)],
        )
        assert result.exit_code == 0


# ── show ────────────────────────────────────────────────────────────────────


class TestConfigShow:
    def test_show_defaults(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["config", "show", "--repo", str(tmp_path)])
        assert result.exit_code == 0
        assert "pattern_fragmentation" in result.output

    def test_show_custom_config(self, runner: CliRunner, valid_config: Path) -> None:
        result = runner.invoke(main, ["config", "show", "--repo", str(valid_config)])
        assert result.exit_code == 0
        assert "fail_on: none" in result.output

    def test_show_invalid_config_exits_1(self, runner: CliRunner, invalid_config: Path) -> None:
        result = runner.invoke(main, ["config", "show", "--repo", str(invalid_config)])
        assert result.exit_code == 1

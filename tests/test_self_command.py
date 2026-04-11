"""Tests for the ``drift self`` command."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from drift.cli import main
from drift.config import DriftConfig
from drift.errors import DriftSystemError
from drift.models import RepoAnalysis

pytestmark = pytest.mark.slow


class TestSelfCommand:
    """Test the ``drift self`` command."""

    def test_self_runs_without_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["self", "--format", "json"])
        # May fail if not run from a git repo, but should not crash
        assert result.exit_code in (0, 1), result.output

    def test_self_json_output_is_valid(self) -> None:
        import json

        runner = CliRunner()
        result = runner.invoke(main, ["self", "--format", "json"])
        if result.exit_code == 0:
            # JSON starts at the first '{' — strip Rich preamble from stderr mixing
            raw = result.output
            json_start = raw.find("{")
            assert json_start >= 0, f"No JSON found in output: {raw[:200]}"
            data = json.loads(raw[json_start:])
            assert "drift_score" in data
            assert "findings" in data

    def test_self_outside_repo_raises_structured_error(self, monkeypatch) -> None:
        from drift.commands import self_analyze as self_cmd

        monkeypatch.setattr(self_cmd.Path, "exists", lambda _self: False)
        runner = CliRunner()
        result = runner.invoke(main, ["self", "--format", "json"])

        assert isinstance(result.exception, DriftSystemError)
        assert result.exception.code == "DRIFT-2001"

    def test_self_excludes_tmp_launch_venv_dirs(self, monkeypatch) -> None:
        captured_excludes: list[str] = []

        def _fake_load(cls, repo_path, config_path=None):
            return DriftConfig(include=["**/*.py"], exclude=[])

        def _fake_analyze(repo_path, cfg, since_days=90, target_path=None):
            captured_excludes.extend(cfg.exclude)
            return RepoAnalysis(
                repo_path=Path(repo_path),
                analyzed_at=datetime.datetime.now(datetime.UTC),
                drift_score=0.1,
            )

        monkeypatch.setattr(DriftConfig, "load", classmethod(_fake_load))
        monkeypatch.setattr("drift.analyzer.analyze_repo", _fake_analyze)

        runner = CliRunner()
        result = runner.invoke(main, ["self", "--format", "json"])

        assert result.exit_code == 0, result.output
        assert "**/.tmp_*venv*/**" in captured_excludes

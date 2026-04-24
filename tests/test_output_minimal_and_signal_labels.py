"""Regression tests for minimal CLI output and signal label rendering."""

from __future__ import annotations

import datetime
import io
import os
import re
import sys
from pathlib import Path

from click.testing import CliRunner
from rich.console import Console

from drift.commands.analyze import analyze
from drift.commands.check import check
from drift.commands.init_cmd import init
from drift.models import RepoAnalysis, SignalType
from drift.output.rich_output import _signal_label, render_summary


class _DummyConfig:
    embeddings_enabled = True
    embedding_model = None
    language = None
    audience = "developer"

    class _RecsOff:
        enabled = False

    recommendations = _RecsOff()

    def severity_gate(self) -> str:
        return "high"


def _sample_analysis(score: float = 0.1) -> RepoAnalysis:
    return RepoAnalysis(
        repo_path=Path("."),
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=score,
        findings=[],
    )


def test_analyze_quiet_emits_minimal_line(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("drift.config.DriftConfig.load", lambda *_args, **_kwargs: _DummyConfig())
    monkeypatch.setattr("drift.analyzer.analyze_repo", lambda *_args, **_kwargs: _sample_analysis())

    runner = CliRunner()
    result = runner.invoke(analyze, ["--repo", str(tmp_path), "--quiet"])

    assert result.exit_code == 0
    out = result.output.strip()
    assert out.startswith("score:")
    assert "severity:" in out
    assert "findings:" in out
    assert "Drift check passed" not in out
    assert "Drift check failed" not in out


def test_check_quiet_emits_minimal_line(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("drift.config.DriftConfig.load", lambda *_args, **_kwargs: _DummyConfig())
    monkeypatch.setattr("drift.analyzer.analyze_diff", lambda *_args, **_kwargs: _sample_analysis())

    runner = CliRunner()
    result = runner.invoke(check, ["--repo", str(tmp_path), "--quiet"])

    assert result.exit_code == 0
    out = result.output.strip()
    assert out.startswith("score:")
    assert "severity:" in out
    assert "findings:" in out
    assert "Drift check passed" not in out
    assert "Drift check failed" not in out


def test_signal_label_fallback_returns_real_signal_id(monkeypatch) -> None:
    import drift.output.rich_output as rich_output

    monkeypatch.delitem(rich_output._SIGNAL_LABELS, SignalType.COHESION_DEFICIT, raising=False)

    assert _signal_label(SignalType.COHESION_DEFICIT) == SignalType.COHESION_DEFICIT.value


def test_analyze_no_color_uses_colorless_console(monkeypatch, tmp_path: Path) -> None:
    import drift.output.rich_output as rich_output

    monkeypatch.setattr("drift.config.DriftConfig.load", lambda *_args, **_kwargs: _DummyConfig())
    monkeypatch.setattr("drift.analyzer.analyze_repo", lambda *_args, **_kwargs: _sample_analysis())

    captured: dict[str, bool] = {}

    def _render_full_report(*_args, **_kwargs) -> None:
        captured["no_color"] = _args[1].no_color

    monkeypatch.setattr(rich_output, "render_full_report", _render_full_report)

    runner = CliRunner()
    result = runner.invoke(analyze, ["--repo", str(tmp_path), "--no-color"])

    assert result.exit_code == 0
    assert captured["no_color"] is True


def test_check_no_color_uses_colorless_console(monkeypatch, tmp_path: Path) -> None:
    import drift.output.rich_output as rich_output

    monkeypatch.setattr("drift.config.DriftConfig.load", lambda *_args, **_kwargs: _DummyConfig())
    monkeypatch.setattr("drift.analyzer.analyze_diff", lambda *_args, **_kwargs: _sample_analysis())

    captured: dict[str, bool] = {}

    def _render_full_report(*_args, **_kwargs) -> None:
        captured["no_color"] = _args[1].no_color

    monkeypatch.setattr(rich_output, "render_full_report", _render_full_report)

    runner = CliRunner()
    result = runner.invoke(check, ["--repo", str(tmp_path), "--no-color"])

    assert result.exit_code == 0
    assert captured["no_color"] is True


def test_analyze_json_threshold_message_uses_ascii_safe_marker(monkeypatch, tmp_path: Path) -> None:
    import drift.commands as commands

    monkeypatch.setattr("drift.config.DriftConfig.load", lambda *_args, **_kwargs: _DummyConfig())
    monkeypatch.setattr("drift.analyzer.analyze_repo", lambda *_args, **_kwargs: _sample_analysis())
    monkeypatch.setattr("drift.scoring.engine.severity_gate_pass", lambda *_args, **_kwargs: False)

    buffer = io.StringIO()
    console = Console(
        file=buffer,
        force_terminal=True,
        width=120,
        safe_box=True,
        emoji=False,
        no_color=True,
    )
    console._drift_ascii_only = True
    monkeypatch.setattr(commands, "make_console", lambda **_kwargs: console)
    monkeypatch.setattr(commands, "console", console)

    original_stdout = sys.stdout
    with open(os.devnull, "w", encoding="cp1252", errors="strict") as redirected:
        try:
            sys.stdout = redirected
            analyze.main(
                args=["--repo", str(tmp_path), "--format", "json", "--exit-zero"],
                prog_name="drift analyze",
                standalone_mode=False,
            )
        finally:
            sys.stdout = original_stdout


def test_render_summary_ascii_fallback_is_windows_safe() -> None:
    analysis = _sample_analysis(0.42)
    analysis.total_files = 5
    analysis.total_functions = 12
    analysis.analysis_duration_seconds = 0.2

    buffer = io.StringIO()
    console = Console(
        file=buffer,
        force_terminal=True,
        width=120,
        safe_box=True,
        emoji=False,
        no_color=True,
    )
    console._drift_ascii_only = True

    render_summary(analysis, console)

    text = re.sub(r"\x1b\[[0-9;]*m", "", buffer.getvalue())
    assert "Grade" in text
    assert all(ord(ch) < 128 for ch in text), text


def test_init_output_ascii_fallback_is_windows_safe(monkeypatch, tmp_path: Path) -> None:
    import drift.commands.init_cmd as init_cmd

    buffer = io.StringIO()
    console = Console(
        file=buffer,
        force_terminal=True,
        width=120,
        safe_box=True,
        emoji=False,
        no_color=True,
    )
    console._drift_ascii_only = True
    monkeypatch.setattr(init_cmd, "console", console)

    runner = CliRunner()
    result = runner.invoke(init, ["--repo", str(tmp_path), "--full"])

    assert result.exit_code == 0
    text = re.sub(r"\x1b\[[0-9;]*m", "", buffer.getvalue())
    assert "file(s) created" in text
    assert all(ord(ch) < 128 for ch in text), text

"""Unit tests for drift completions command."""

from __future__ import annotations

from click.testing import CliRunner

from drift.commands.completions import completions


def test_completions_bash_exit_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(completions, ["bash"])
    assert result.exit_code == 0


def test_completions_zsh_exit_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(completions, ["zsh"])
    assert result.exit_code == 0


def test_completions_fish_exit_zero() -> None:
    runner = CliRunner()
    result = runner.invoke(completions, ["fish"])
    assert result.exit_code == 0


def test_completions_invalid_shell() -> None:
    runner = CliRunner()
    result = runner.invoke(completions, ["tcsh"])
    assert result.exit_code != 0


def test_completions_powershell_unsupported() -> None:
    runner = CliRunner()
    result = runner.invoke(completions, ["powershell"])
    assert result.exit_code != 0

"""Tests for Phase-A DX features: explain, code snippets, exit codes, quiet mode."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from drift import cli
from drift.commands.explain import _LOOKUP, _SIGNAL_INFO, explain
from drift.output.rich_output import _read_code_snippet

# ---------------------------------------------------------------------------
# drift explain
# ---------------------------------------------------------------------------


class TestExplainSignalData:
    """Validate the signal reference data completeness."""

    def test_all_13_signals_present(self) -> None:
        assert len(_SIGNAL_INFO) == 13

    @pytest.mark.parametrize("abbr", list(_SIGNAL_INFO.keys()))
    def test_each_signal_has_required_keys(self, abbr: str) -> None:
        info = _SIGNAL_INFO[abbr]
        required = (
            "signal_type", "name", "weight", "description",
            "detects", "example", "fix_hint",
        )
        for key in required:
            assert key in info, f"{abbr} missing key: {key}"

    @pytest.mark.parametrize("abbr", list(_SIGNAL_INFO.keys()))
    def test_lookup_by_abbreviation(self, abbr: str) -> None:
        assert abbr.lower() in _LOOKUP

    @pytest.mark.parametrize("abbr", list(_SIGNAL_INFO.keys()))
    def test_lookup_by_signal_type(self, abbr: str) -> None:
        signal_type = _SIGNAL_INFO[abbr]["signal_type"]
        assert signal_type in _LOOKUP


class TestExplainCLI:
    """Test the Click command interface for explain."""

    def test_explain_list_runs(self, cli_runner) -> None:
        result = cli_runner.invoke(explain, ["--list"])
        assert result.exit_code == 0

    def test_explain_known_signal(self, cli_runner) -> None:
        result = cli_runner.invoke(explain, ["PFS"])
        assert result.exit_code == 0
        assert "Pattern Fragmentation" in result.output

    def test_explain_unknown_signal(self, cli_runner) -> None:
        result = cli_runner.invoke(explain, ["NONEXISTENT"])
        assert result.exit_code != 0

    def test_explain_case_insensitive(self, cli_runner) -> None:
        result = cli_runner.invoke(explain, ["pfs"])
        assert result.exit_code == 0
        assert "Pattern Fragmentation" in result.output

    def test_explain_by_signal_type(self, cli_runner) -> None:
        result = cli_runner.invoke(explain, ["pattern_fragmentation"])
        assert result.exit_code == 0
        assert "Pattern Fragmentation" in result.output

    def test_explain_no_args_shows_list(self, cli_runner) -> None:
        result = cli_runner.invoke(explain, [])
        assert result.exit_code == 0
        # Should show multi-signal table
        assert "PFS" in result.output
        assert "AVS" in result.output


# ---------------------------------------------------------------------------
# Code snippets
# ---------------------------------------------------------------------------


class TestCodeSnippets:
    """Test _read_code_snippet() helper."""

    def test_reads_file_at_target_line(self, tmp_path: Path) -> None:
        src = tmp_path / "example.py"
        src.write_text("line1\nline2\nline3\nline4\nline5\n")

        result = _read_code_snippet(src, 3, context=1, max_lines=3)
        assert result is not None
        plain = result.plain
        assert "line2" in plain  # context before
        assert "line3" in plain  # target
        assert "line4" in plain  # context after

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.py"
        assert _read_code_snippet(missing, 1) is None

    def test_returns_none_when_no_file_path(self) -> None:
        assert _read_code_snippet(None, 1) is None

    def test_returns_none_when_no_line(self, tmp_path: Path) -> None:
        src = tmp_path / "example.py"
        src.write_text("line1\n")
        assert _read_code_snippet(src, None) is None

    def test_resolves_relative_path(self, tmp_path: Path) -> None:
        sub = tmp_path / "src"
        sub.mkdir()
        src = sub / "mod.py"
        src.write_text("a\nb\nc\n")

        result = _read_code_snippet(Path("src/mod.py"), 2, repo_root=tmp_path)
        assert result is not None
        assert "b" in result.plain

    def test_marker_on_target_line(self, tmp_path: Path) -> None:
        src = tmp_path / "example.py"
        src.write_text("aaa\nbbb\nccc\n")

        result = _read_code_snippet(src, 2, context=1, max_lines=3)
        assert result is not None
        plain = result.plain
        # The target line should have the → marker
        for line in plain.splitlines():
            if "bbb" in line:
                assert "→" in line
            elif line.strip():
                assert "→" not in line


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------


class TestExitCodes:
    """Verify exit code 2 for internal errors."""

    def test_file_not_found_exits_2(self, monkeypatch, capsys) -> None:
        def _raise(*a, **kw):
            raise FileNotFoundError("gone")

        monkeypatch.setattr(cli, "main", _raise)

        with pytest.raises(SystemExit) as exc_info:
            cli.safe_main()

        assert exc_info.value.code == 2

    def test_generic_exception_exits_2(self, monkeypatch, capsys) -> None:
        def _raise(*a, **kw):
            raise RuntimeError("boom")

        monkeypatch.setattr(cli, "main", _raise)
        logging.getLogger().setLevel(logging.WARNING)

        with pytest.raises(SystemExit) as exc_info:
            cli.safe_main()

        assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_runner():
    """Click CLI test runner."""
    from click.testing import CliRunner

    return CliRunner()

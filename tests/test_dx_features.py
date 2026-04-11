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

    def test_all_23_signals_present(self) -> None:
        assert len(_SIGNAL_INFO) == 23

    @pytest.mark.parametrize("abbr", list(_SIGNAL_INFO.keys()))
    def test_each_signal_has_required_keys(self, abbr: str) -> None:
        info = _SIGNAL_INFO[abbr]
        required = (
            "signal_type",
            "name",
            "weight",
            "description",
            "detects",
            "example",
            "fix_hint",
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

    @pytest.mark.parametrize("abbr", ["GCD", "NBV"])
    def test_gcd_nbv_include_trigger_contract_metadata(self, abbr: str) -> None:
        info = _SIGNAL_INFO[abbr]
        assert "trigger_contract" in info
        contract = info["trigger_contract"]
        assert isinstance(contract, dict)
        assert "thresholds" in contract


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

    @pytest.mark.parametrize("abbr", ["GCD", "NBV"])
    def test_explain_shows_trigger_contract_for_signal(self, cli_runner, abbr: str) -> None:
        result = cli_runner.invoke(explain, [abbr])
        assert result.exit_code == 0
        assert "Trigger contract" in result.output
        assert "Thresholds" in result.output


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
    """Verify structured exit codes for internal errors."""

    def test_file_not_found_exits_4(self, monkeypatch, capsys) -> None:
        def _raise(*a, **kw):
            raise FileNotFoundError("gone")

        monkeypatch.setattr(cli, "main", _raise)

        with pytest.raises(SystemExit) as exc_info:
            cli.safe_main()

        assert exc_info.value.code == 4

    def test_generic_exception_exits_3(self, monkeypatch, capsys) -> None:
        def _raise(*a, **kw):
            raise RuntimeError("boom")

        monkeypatch.setattr(cli, "main", _raise)
        logging.getLogger().setLevel(logging.WARNING)

        with pytest.raises(SystemExit) as exc_info:
            cli.safe_main()

        assert exc_info.value.code == 3


# ---------------------------------------------------------------------------
# DriftError exit codes
# ---------------------------------------------------------------------------


class TestDriftErrorExitCodes:
    """Verify structured error exceptions produce correct exit codes."""

    def test_config_error_exits_2(self, monkeypatch, capsys) -> None:
        from drift.errors import DriftConfigError

        def _raise(*a, **kw):
            raise DriftConfigError(
                "DRIFT-1001", "bad config", config_path="drift.yaml", field="x", reason="r", line=1
            )

        monkeypatch.setattr(cli, "main", _raise)

        with pytest.raises(SystemExit) as exc_info:
            cli.safe_main()

        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "DRIFT-1001" in captured.err

    def test_system_error_exits_4(self, monkeypatch, capsys) -> None:
        from drift.errors import DriftSystemError

        def _raise(*a, **kw):
            raise DriftSystemError("DRIFT-2001", "missing repo", path="/nonexistent")

        monkeypatch.setattr(cli, "main", _raise)

        with pytest.raises(SystemExit) as exc_info:
            cli.safe_main()

        assert exc_info.value.code == 4
        captured = capsys.readouterr()
        assert "DRIFT-2001" in captured.err

    def test_analysis_error_exits_3(self, monkeypatch, capsys) -> None:
        from drift.errors import DriftAnalysisError

        def _raise(*a, **kw):
            raise DriftAnalysisError(
                "DRIFT-3001", "parse failed", path="bad.py", line=1, reason="syntax"
            )

        monkeypatch.setattr(cli, "main", _raise)

        with pytest.raises(SystemExit) as exc_info:
            cli.safe_main()

        assert exc_info.value.code == 3
        captured = capsys.readouterr()
        assert "DRIFT-3001" in captured.err


# ---------------------------------------------------------------------------
# Error code explain
# ---------------------------------------------------------------------------


class TestExplainErrorCodes:
    """Test drift explain for error codes."""

    def test_explain_error_code(self, cli_runner) -> None:
        result = cli_runner.invoke(explain, ["DRIFT-1001"])
        assert result.exit_code == 0
        assert "DRIFT-1001" in result.output
        assert "User Error" in result.output

    def test_explain_error_code_case_insensitive(self, cli_runner) -> None:
        result = cli_runner.invoke(explain, ["drift-1001"])
        assert result.exit_code == 0
        assert "DRIFT-1001" in result.output

    def test_explain_unknown_error_code(self, cli_runner) -> None:
        result = cli_runner.invoke(explain, ["DRIFT-9999"])
        assert result.exit_code != 0
        assert "Unknown error code" in result.output

    def test_explain_system_error_code(self, cli_runner) -> None:
        result = cli_runner.invoke(explain, ["DRIFT-2001"])
        assert result.exit_code == 0
        assert "System Error" in result.output

    def test_explain_drift_2010_interpolates_placeholder_defaults(self, cli_runner) -> None:
        result = cli_runner.invoke(explain, ["DRIFT-2010"])
        assert result.exit_code == 0
        assert "{package}" not in result.output
        assert "{extra}" not in result.output
        assert "Optional dependency missing: mcp" in result.output
        assert "pip install drift-analyzer[mcp]" in result.output


# ---------------------------------------------------------------------------
# Error code registry
# ---------------------------------------------------------------------------


class TestErrorRegistry:
    """Test the error code system itself."""

    def test_error_format(self) -> None:
        from drift.errors import ERROR_REGISTRY

        info = ERROR_REGISTRY["DRIFT-1001"]
        msg = info.format(
            config_path="drift.yaml", field="weights.pfs", reason="expects float", line=12
        )
        assert "[DRIFT-1001]" in msg
        assert "weights.pfs" in msg
        assert "→" in msg

    def test_drift_error_detail_includes_context(self) -> None:
        from drift.errors import DriftConfigError

        exc = DriftConfigError("DRIFT-1001", "bad value", context="  → 12 │   pfs: bad")
        assert "→ 12" in exc.detail
        assert "DRIFT-1001" in exc.detail

    def test_drift_error_hint(self) -> None:
        from drift.errors import DriftConfigError

        exc = DriftConfigError("DRIFT-1001", "bad value")
        assert "drift explain DRIFT-1001" in exc.hint

    def test_yaml_context_snippet(self) -> None:
        from drift.errors import yaml_context_snippet

        raw = "a: 1\nb: 2\nc: 3\nd: 4\ne: 5\n"
        snippet = yaml_context_snippet(raw, 3, context=1)
        assert "→" in snippet
        assert "c: 3" in snippet
        assert "b: 2" in snippet
        assert "d: 4" in snippet

    def test_find_yaml_line(self) -> None:
        from drift.errors import _find_yaml_line

        raw = "weights:\n  pattern_fragmentation: 0.16\n  architecture_violation: bad\n"
        line = _find_yaml_line(raw, ("weights", "architecture_violation"))
        assert line == 3


# ---------------------------------------------------------------------------
# Code snippet end_line support
# ---------------------------------------------------------------------------


class TestCodeSnippetEndLine:
    """Test end_line support in _read_code_snippet."""

    def test_multi_line_highlight(self, tmp_path: Path) -> None:
        src = tmp_path / "multi.py"
        src.write_text("line1\nline2\nline3\nline4\nline5\nline6\n")
        result = _read_code_snippet(src, 2, end_line=4, context=1, max_lines=6)
        assert result is not None
        plain = result.plain
        # Lines 2-4 should have arrow markers
        for line in plain.splitlines():
            if "line2" in line or "line3" in line or "line4" in line:
                assert "→" in line
            elif "line1" in line or "line5" in line:
                assert "→" not in line


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_runner():
    """Click CLI test runner."""
    from click.testing import CliRunner

    return CliRunner()


# ---------------------------------------------------------------------------
# #69 explain --output writes JSON file
# ---------------------------------------------------------------------------


class TestExplainOutput:
    """Test -o / --output option on explain command."""

    def test_explain_signal_output_file(self, cli_runner, tmp_path) -> None:
        import json

        out = tmp_path / "explain.json"
        result = cli_runner.invoke(explain, ["PFS", "-o", str(out)])
        assert result.exit_code == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["abbreviation"] == "PFS"
        assert "description" in data
        assert "fix_hint" in data

    @pytest.mark.parametrize("abbr", ["GCD", "NBV"])
    def test_explain_signal_output_includes_trigger_contract(
        self,
        cli_runner,
        tmp_path,
        abbr: str,
    ) -> None:
        import json

        out = tmp_path / f"{abbr.lower()}_explain.json"
        result = cli_runner.invoke(explain, [abbr, "-o", str(out)])
        assert result.exit_code == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "trigger_contract" in data
        assert "thresholds" in data["trigger_contract"]

    def test_explain_list_output_file(self, cli_runner, tmp_path) -> None:
        import json

        out = tmp_path / "signals.json"
        result = cli_runner.invoke(explain, ["--list", "-o", str(out)])
        assert result.exit_code == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 23

    def test_explain_error_code_output_file(self, cli_runner, tmp_path) -> None:
        import json

        out = tmp_path / "error.json"
        result = cli_runner.invoke(explain, ["DRIFT-1001", "-o", str(out)])
        assert result.exit_code == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["code"] == "DRIFT-1001"

    def test_explain_error_code_output_file_interpolates_defaults(
        self,
        cli_runner,
        tmp_path,
    ) -> None:
        import json

        out = tmp_path / "error_2010.json"
        result = cli_runner.invoke(explain, ["DRIFT-2010", "-o", str(out)])
        assert result.exit_code == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["code"] == "DRIFT-2010"
        assert "{extra}" not in data["action"]
        assert data["action"] == "Install with: pip install drift-analyzer[mcp]"


# ---------------------------------------------------------------------------
# #72 passlib warning suppression
# ---------------------------------------------------------------------------


class TestWarningsSuppression:
    """Verify third-party warnings are suppressed at import time."""

    def test_passlib_warnings_filtered(self) -> None:
        """cli.py suppresses SyntaxWarnings at import time."""
        import ast
        from pathlib import Path

        cli_path = Path(cli.__file__)
        tree = ast.parse(cli_path.read_text(encoding="utf-8"))

        # Find a call to warnings.filterwarnings that targets SyntaxWarning
        found = False
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "filterwarnings"
            ):
                for kw in node.keywords:
                    if (
                        kw.arg == "category"
                        and isinstance(kw.value, ast.Name)
                        and kw.value.id == "SyntaxWarning"
                    ):
                        found = True
                        break
                if not found:
                    for arg in node.args:
                        if isinstance(arg, ast.Name) and arg.id == "SyntaxWarning":
                            found = True
                            break
                if found:
                    found = True
                    break
        assert found, "cli.py must contain warnings.filterwarnings for SyntaxWarning"

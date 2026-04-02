"""Tests for drift MCP server and copilot-context modules."""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from drift.copilot_context import (
    MARKER_BEGIN,
    MARKER_END,
    generate_instructions,
    merge_into_file,
)
from drift.models import (
    Finding,
    ModuleScore,
    RepoAnalysis,
    Severity,
    SignalType,
    TrendContext,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _analysis(tmp_path: Path) -> RepoAnalysis:
    """Build a minimal RepoAnalysis with diverse findings."""
    findings = [
        Finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            severity=Severity.HIGH,
            score=0.7,
            title="Layer violation: api → db",
            description="api/routes.py imports directly from db/models.py",
            file_path=Path("api/routes.py"),
            start_line=2,
            fix="Use service layer instead of importing db models directly.",
            impact=0.8,
        ),
        Finding(
            signal_type=SignalType.ARCHITECTURE_VIOLATION,
            severity=Severity.MEDIUM,
            score=0.5,
            title="Layer violation: api → db (second)",
            description="Another violation",
            file_path=Path("api/handlers.py"),
            start_line=5,
            fix="Route through service layer.",
            impact=0.6,
        ),
        Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.MEDIUM,
            score=0.5,
            title="3 error-handling variants in services/",
            description="Inconsistent exception patterns",
            file_path=Path("services/payment.py"),
            start_line=10,
            fix="Consolidate to one error-handling pattern per module.",
            impact=0.5,
        ),
        Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.MEDIUM,
            score=0.45,
            title="2 HTTP client patterns",
            description="Mixed httpx and requests usage",
            file_path=Path("services/external.py"),
            start_line=1,
            fix="Standardize on httpx for HTTP requests.",
            impact=0.4,
        ),
        Finding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            severity=Severity.MEDIUM,
            score=0.45,
            title="Bare except in services/",
            description="10 broad exception handlers",
            file_path=Path("services/payment.py"),
            start_line=30,
            impact=0.3,
        ),
        Finding(
            signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
            severity=Severity.MEDIUM,
            score=0.42,
            title="Bare except in api/",
            description="5 broad exception handlers",
            file_path=Path("api/routes.py"),
            start_line=15,
            impact=0.25,
        ),
        # Low-score finding (should be filtered out)
        Finding(
            signal_type=SignalType.GUARD_CLAUSE_DEFICIT,
            severity=Severity.LOW,
            score=0.2,
            title="Missing guards",
            description="Low score finding",
            file_path=Path("utils/helpers.py"),
            impact=0.1,
        ),
        # Temporal signal (should be excluded — not actionable)
        Finding(
            signal_type=SignalType.TEMPORAL_VOLATILITY,
            severity=Severity.HIGH,
            score=0.8,
            title="High churn on payment.py",
            description="47 commits in 30 days",
            file_path=Path("services/payment.py"),
            impact=0.7,
        ),
    ]

    modules = [
        ModuleScore(
            path=Path("services"),
            drift_score=0.65,
            findings=findings[:3],
        ),
        ModuleScore(
            path=Path("api"),
            drift_score=0.45,
            findings=findings[3:5],
        ),
    ]

    return RepoAnalysis(
        repo_path=tmp_path,
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=0.55,
        findings=findings,
        module_scores=modules,
        total_files=20,
        total_functions=50,
        trend=TrendContext(
            previous_score=0.52,
            delta=0.03,
            direction="degrading",
            recent_scores=[0.50, 0.52, 0.55],
            history_depth=3,
            transition_ratio=0.6,
        ),
    )


# ---------------------------------------------------------------------------
# copilot_context — generate_instructions
# ---------------------------------------------------------------------------


class TestGenerateInstructions:
    def test_contains_markers(self, _analysis: RepoAnalysis) -> None:
        result = generate_instructions(_analysis)
        assert MARKER_BEGIN in result
        assert MARKER_END in result

    def test_includes_actionable_signals(self, _analysis: RepoAnalysis) -> None:
        result = generate_instructions(_analysis)
        assert "Layer Boundaries" in result
        assert "Code Pattern Consistency" in result
        assert "Exception Handling" in result

    def test_excludes_temporal_signals(self, _analysis: RepoAnalysis) -> None:
        result = generate_instructions(_analysis)
        # Temporal volatility is not actionable for instructions
        assert "High churn" not in result
        assert "47 commits" not in result

    def test_excludes_low_score_findings(self, _analysis: RepoAnalysis) -> None:
        result = generate_instructions(_analysis)
        # Guard clause finding has score 0.2, should be filtered
        assert "Missing guards" not in result

    def test_includes_drift_status(self, _analysis: RepoAnalysis) -> None:
        result = generate_instructions(_analysis)
        assert "Drift Score" in result
        assert "0.55" in result
        assert "degrading" in result

    def test_includes_worst_module(self, _analysis: RepoAnalysis) -> None:
        result = generate_instructions(_analysis)
        assert "services" in result

    def test_empty_findings_produces_clean_output(self, tmp_path: Path) -> None:
        analysis = RepoAnalysis(
            repo_path=tmp_path,
            analyzed_at=datetime.datetime.now(tz=datetime.UTC),
            drift_score=0.1,
        )
        result = generate_instructions(analysis)
        assert MARKER_BEGIN in result
        assert "No significant architectural issues" in result


# ---------------------------------------------------------------------------
# copilot_context — merge_into_file
# ---------------------------------------------------------------------------


class TestMergeIntoFile:
    def test_creates_new_file(self, tmp_path: Path) -> None:
        target = tmp_path / ".github" / "copilot-instructions.md"
        section = f"{MARKER_BEGIN}\ntest content\n{MARKER_END}\n"
        changed = merge_into_file(target, section)
        assert changed is True
        assert target.exists()
        assert "test content" in target.read_text()

    def test_replaces_existing_markers(self, tmp_path: Path) -> None:
        target = tmp_path / "instructions.md"
        original = (
            "# My Instructions\n\nHand-written stuff.\n\n"
            f"{MARKER_BEGIN}\nold drift content\n{MARKER_END}\n\n"
            "More hand-written content.\n"
        )
        target.write_text(original)

        new_section = f"{MARKER_BEGIN}\nnew drift content\n{MARKER_END}\n"
        changed = merge_into_file(target, new_section)
        assert changed is True

        result = target.read_text()
        assert "new drift content" in result
        assert "old drift content" not in result
        assert "Hand-written stuff." in result
        assert "More hand-written content." in result

    def test_appends_when_no_markers(self, tmp_path: Path) -> None:
        target = tmp_path / "instructions.md"
        target.write_text("# Existing content\n")

        section = f"{MARKER_BEGIN}\ndrift section\n{MARKER_END}\n"
        changed = merge_into_file(target, section)
        assert changed is True

        result = target.read_text()
        assert "# Existing content" in result
        assert "drift section" in result

    def test_no_change_when_identical(self, tmp_path: Path) -> None:
        target = tmp_path / "instructions.md"
        section = f"{MARKER_BEGIN}\ncontent\n{MARKER_END}\n"
        target.write_text(section)

        changed = merge_into_file(target, section)
        assert changed is False

    def test_no_merge_overwrites(self, tmp_path: Path) -> None:
        target = tmp_path / "instructions.md"
        target.write_text("old content that should disappear")

        section = f"{MARKER_BEGIN}\nnew only\n{MARKER_END}\n"
        changed = merge_into_file(target, section, no_merge=True)
        assert changed is True
        assert target.read_text() == section


# ---------------------------------------------------------------------------
# MCP server — tool handlers (unit tests, no MCP transport)
# ---------------------------------------------------------------------------


class TestMcpServerHelpers:
    """Test MCP server tool functions are importable and well-formed."""

    def test_mcp_tools_importable(self) -> None:
        """All five v2 MCP tools can be imported."""
        from drift.mcp_server import (
            drift_diff,
            drift_explain,
            drift_fix_plan,
            drift_scan,
            drift_validate,
        )

        # They should all be callable functions
        assert callable(drift_scan)
        assert callable(drift_diff)
        assert callable(drift_explain)
        assert callable(drift_fix_plan)
        assert callable(drift_validate)

    def test_drift_explain_returns_json(self) -> None:
        """drift_explain returns valid JSON for a known signal."""
        import json as _json

        from drift.mcp_server import drift_explain

        result = _json.loads(drift_explain("PFS"))
        assert "name" in result
        assert "description" in result

    def test_drift_explain_unknown_topic(self) -> None:
        """drift_explain handles unknown topics gracefully."""
        import json as _json

        from drift.mcp_server import drift_explain

        result = _json.loads(drift_explain("NONEXISTENT_THING"))
        # Should still return valid JSON without crashing
        assert isinstance(result, dict)

    def test_drift_explain_error_code_interpolates_defaults(self) -> None:
        """drift_explain resolves DRIFT-2010 template placeholders."""
        import json as _json

        from drift.mcp_server import drift_explain

        result = _json.loads(drift_explain("DRIFT-2010"))
        assert result["error_code"] == "DRIFT-2010"
        assert result["summary"] == "Optional dependency missing: mcp"
        assert result["action"] == "Install with: pip install drift-analyzer[mcp]"


# ---------------------------------------------------------------------------
# CLI command — smoke tests
# ---------------------------------------------------------------------------


class TestCLICommands:
    def test_mcp_help(self) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["mcp", "--help"])
        assert result.exit_code == 0
        assert "MCP server" in result.output

    def test_mcp_no_args_shows_usage(self) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["mcp"])
        assert "drift mcp --serve" in result.output
        assert "drift mcp --list" in result.output
        assert "drift-analyzer[mcp]" in result.output

    def test_mcp_list_shows_tools_without_starting_server(self) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["mcp", "--list"])

        assert result.exit_code == 0
        assert "drift_scan" in result.output
        assert "drift_diff" in result.output
        assert "drift_validate" in result.output

    def test_mcp_schema_outputs_tool_parameters(self) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["mcp", "--schema"])

        assert result.exit_code == 0
        assert '"tools"' in result.output
        assert '"name": "drift_scan"' in result.output
        assert '"parameters"' in result.output

    def test_mcp_modes_are_mutually_exclusive(self) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["mcp", "--serve", "--list"])

        assert result.exit_code != 0
        assert "Use only one mode" in result.output

    def test_mcp_missing_extra_raises_structured_error(self, monkeypatch) -> None:
        from click.testing import CliRunner

        from drift import mcp_server
        from drift.cli import main
        from drift.errors import DriftSystemError

        def _raise_missing_dependency() -> None:
            raise RuntimeError("requires optional dependency 'mcp'")

        monkeypatch.setattr(mcp_server, "main", _raise_missing_dependency)

        runner = CliRunner()
        result = runner.invoke(main, ["mcp", "--serve"])

        assert isinstance(result.exception, DriftSystemError)
        assert result.exception.code == "DRIFT-2010"

    def test_copilot_context_help(self) -> None:
        from click.testing import CliRunner

        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["copilot-context", "--help"])
        assert result.exit_code == 0
        assert "copilot" in result.output.lower()

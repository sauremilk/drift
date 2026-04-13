"""Tests for multi-format agent context generation (C1)."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from unittest.mock import MagicMock

from drift.copilot_context import (
    VALID_TARGETS,
    generate_claude_instructions,
    generate_cursorrules,
    generate_for_target,
    target_default_path,
)
from drift.models import Finding, RepoAnalysis, Severity


def _make_analysis(
    *,
    findings: list[Finding] | None = None,
    drift_score: float = 0.45,
    severity: Severity = Severity.MEDIUM,
) -> RepoAnalysis:
    """Build a minimal RepoAnalysis for testing."""
    analysis = MagicMock(spec=RepoAnalysis)
    analysis.drift_score = drift_score
    analysis.severity = severity
    analysis.findings = findings or []
    analysis.trend = None
    analysis.module_scores = []
    return analysis


def _make_finding(
    *,
    signal_type: str = "architecture_violation",
    score: float = 0.7,
    title: str = "Test finding",
    description: str = "Test description",
    fix: str = "Fix this",
    file_path: str = "src/foo.py",
    severity: Severity = Severity.HIGH,
) -> Finding:
    """Build a minimal Finding."""
    f = MagicMock(spec=Finding)
    f.signal_type = signal_type
    f.score = score
    f.title = title
    f.description = description
    f.fix = fix
    f.file_path = PurePosixPath(file_path) if file_path else None
    f.severity = severity
    f.rule_id = "TEST-001"
    f.start_line = 10
    return f


class TestValidTargets:
    def test_contains_expected(self) -> None:
        assert "copilot" in VALID_TARGETS
        assert "cursor" in VALID_TARGETS
        assert "windsurf" in VALID_TARGETS
        assert "claude" in VALID_TARGETS
        assert "agents" in VALID_TARGETS

    def test_excludes_all(self) -> None:
        # "all" is a CLI choice but not a generate target
        assert "all" not in VALID_TARGETS


class TestCursorRulesGeneration:
    def test_no_findings_generates_header(self) -> None:
        analysis = _make_analysis()
        result = generate_cursorrules(analysis)
        assert "# Architectural constraints (drift-generated)" in result
        assert "No significant architectural issues" in result

    def test_with_findings_generates_rules(self) -> None:
        findings = [
            _make_finding(signal_type="architecture_violation"),
            _make_finding(signal_type="architecture_violation", fix="Don't cross layers"),
        ]
        analysis = _make_analysis(findings=findings)
        result = generate_cursorrules(analysis)
        assert "# [AVS]" in result
        assert "Fix this" in result

    def test_output_is_comment_style(self) -> None:
        findings = [
            _make_finding(),
            _make_finding(),
        ]
        analysis = _make_analysis(findings=findings)
        result = generate_cursorrules(analysis)
        # All non-empty lines should be comments
        for line in result.strip().splitlines():
            if line.strip():
                assert line.startswith("#")


class TestClaudeInstructionsGeneration:
    def test_no_findings_generates_header(self) -> None:
        analysis = _make_analysis()
        result = generate_claude_instructions(analysis)
        assert "# Architectural Constraints" in result
        assert "No significant architectural issues" in result

    def test_with_findings_generates_rules(self) -> None:
        findings = [
            _make_finding(signal_type="architecture_violation"),
            _make_finding(signal_type="architecture_violation"),
        ]
        analysis = _make_analysis(findings=findings)
        result = generate_claude_instructions(analysis)
        assert "## Rules" in result
        assert "**AVS**" in result

    def test_markdown_format(self) -> None:
        findings = [
            _make_finding(),
            _make_finding(),
        ]
        analysis = _make_analysis(findings=findings)
        result = generate_claude_instructions(analysis)
        assert result.startswith("# ")
        assert "- **" in result


class TestGenerateForTarget:
    def test_copilot_uses_instructions(self) -> None:
        analysis = _make_analysis()
        result = generate_for_target("copilot", analysis)
        assert "<!-- drift:begin" in result

    def test_cursor_uses_cursorrules(self) -> None:
        analysis = _make_analysis()
        result = generate_for_target("cursor", analysis)
        assert result.startswith("# Architectural constraints")

    def test_windsurf_uses_cursorrules_format(self) -> None:
        analysis = _make_analysis()
        result = generate_for_target("windsurf", analysis)
        assert result.startswith("# Architectural constraints")

    def test_claude_uses_claude_format(self) -> None:
        analysis = _make_analysis()
        result = generate_for_target("claude", analysis)
        assert result.startswith("# Architectural Constraints")

    def test_agents_uses_claude_format(self) -> None:
        analysis = _make_analysis()
        result = generate_for_target("agents", analysis)
        assert result.startswith("# Architectural Constraints")


class TestTargetDefaultPath:
    def test_copilot_path(self) -> None:
        p = target_default_path("copilot", Path("/repo"))
        assert p == Path("/repo/.github/copilot-instructions.md")

    def test_cursor_path(self) -> None:
        p = target_default_path("cursor", Path("/repo"))
        assert p == Path("/repo/.cursorrules")

    def test_windsurf_path(self) -> None:
        p = target_default_path("windsurf", Path("/repo"))
        assert p == Path("/repo/.windsurfrules")

    def test_claude_path(self) -> None:
        p = target_default_path("claude", Path("/repo"))
        assert p == Path("/repo/CLAUDE.md")

    def test_agents_path(self) -> None:
        p = target_default_path("agents", Path("/repo"))
        assert p == Path("/repo/AGENTS.md")

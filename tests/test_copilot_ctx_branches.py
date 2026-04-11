"""Coverage tests for copilot_context module — _format_rule, generate_*, merge_into_file."""

from __future__ import annotations

import datetime
from pathlib import Path

from drift.copilot_context import (
    MARKER_BEGIN,
    MARKER_END,
    _format_rule,
    _heading,
    generate_claude_instructions,
    generate_cursorrules,
    generate_for_target,
    generate_instructions,
    merge_into_file,
    target_default_path,
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
# Helpers
# ---------------------------------------------------------------------------


def _finding(
    signal: str = SignalType.ARCHITECTURE_VIOLATION,
    *,
    file_path: str | None = "src/foo.py",
    title: str = "Finding title",
    description: str = "Finding desc",
    fix: str | None = None,
    score: float = 0.8,
) -> Finding:
    return Finding(
        signal_type=signal,
        severity=Severity.HIGH,
        score=score,
        title=title,
        description=description,
        file_path=Path(file_path) if file_path else None,
        fix=fix,
    )


def _analysis(
    findings: list[Finding] | None = None,
    drift_score: float = 0.3,
    trend: TrendContext | None = None,
    module_scores: list[ModuleScore] | None = None,
) -> RepoAnalysis:
    return RepoAnalysis(
        repo_path=Path("."),
        analyzed_at=datetime.datetime.now(tz=datetime.UTC),
        drift_score=drift_score,
        findings=findings or [],
        trend=trend,
        module_scores=module_scores or [],
    )


# ---------------------------------------------------------------------------
# _heading
# ---------------------------------------------------------------------------


class TestHeading:
    def test_basic_format(self):
        result = _heading("Layer Boundaries", SignalType.ARCHITECTURE_VIOLATION)
        assert "### Layer Boundaries (AVS)" in result


# ---------------------------------------------------------------------------
# _format_rule — branch coverage for each signal type
# ---------------------------------------------------------------------------


class TestFormatRule:
    def test_empty_findings(self):
        assert _format_rule(SignalType.ARCHITECTURE_VIOLATION, []) is None

    def test_architecture_violation_with_fix(self):
        f = _finding(fix="Use DI instead")
        result = _format_rule(SignalType.ARCHITECTURE_VIOLATION, [f])
        assert "Layer Boundaries" in result
        assert "Use DI instead" in result

    def test_architecture_violation_without_fix(self):
        f = _finding(fix=None, description="bad import")
        result = _format_rule(SignalType.ARCHITECTURE_VIOLATION, [f])
        assert "bad import" in result

    def test_pattern_fragmentation_with_fix(self):
        f = _finding(signal=SignalType.PATTERN_FRAGMENTATION, fix="Use pattern X")
        result = _format_rule(SignalType.PATTERN_FRAGMENTATION, [f])
        assert "Pattern Consistency" in result
        assert "Use pattern X" in result

    def test_pattern_fragmentation_without_fix(self):
        f = _finding(signal=SignalType.PATTERN_FRAGMENTATION, fix=None, title="PFS title")
        result = _format_rule(SignalType.PATTERN_FRAGMENTATION, [f])
        assert "PFS title" in result

    def test_naming_contract_with_fix(self):
        f = _finding(signal=SignalType.NAMING_CONTRACT_VIOLATION, fix="Rename foo")
        result = _format_rule(SignalType.NAMING_CONTRACT_VIOLATION, [f])
        assert "Naming Conventions" in result

    def test_naming_contract_without_fix(self):
        f = _finding(signal=SignalType.NAMING_CONTRACT_VIOLATION, fix=None, title="NCV title")
        result = _format_rule(SignalType.NAMING_CONTRACT_VIOLATION, [f])
        assert "NCV title" in result

    def test_guard_clause_deficit(self):
        f = _finding(signal=SignalType.GUARD_CLAUSE_DEFICIT, file_path="src/a.py")
        result = _format_rule(SignalType.GUARD_CLAUSE_DEFICIT, [f])
        assert "Input Validation" in result
        assert "Priority modules" in result

    def test_broad_exception_monoculture(self):
        f = _finding(signal=SignalType.BROAD_EXCEPTION_MONOCULTURE, file_path="src/b.py")
        result = _format_rule(SignalType.BROAD_EXCEPTION_MONOCULTURE, [f])
        assert "Exception Handling" in result

    def test_doc_impl_drift(self):
        f = _finding(signal=SignalType.DOC_IMPL_DRIFT, description="Outdated docs")
        result = _format_rule(SignalType.DOC_IMPL_DRIFT, [f])
        assert "Documentation Alignment" in result

    def test_mutant_duplicate(self):
        f = _finding(signal=SignalType.MUTANT_DUPLICATE, file_path="src/c.py")
        result = _format_rule(SignalType.MUTANT_DUPLICATE, [f])
        assert "Deduplication" in result
        assert "Files with duplicates" in result

    def test_explainability_deficit(self):
        f = _finding(signal=SignalType.EXPLAINABILITY_DEFICIT, file_path="src/d.py")
        result = _format_rule(SignalType.EXPLAINABILITY_DEFICIT, [f])
        assert "Code Documentation" in result

    def test_bypass_accumulation(self):
        f = _finding(signal=SignalType.BYPASS_ACCUMULATION)
        result = _format_rule(SignalType.BYPASS_ACCUMULATION, [f])
        assert "TODO" in result

    def test_exception_contract_drift_with_fix(self):
        f = _finding(signal=SignalType.EXCEPTION_CONTRACT_DRIFT, fix="Align exceptions")
        result = _format_rule(SignalType.EXCEPTION_CONTRACT_DRIFT, [f])
        assert "Exception Contracts" in result
        assert "Align exceptions" in result

    def test_exception_contract_drift_without_fix(self):
        f = _finding(signal=SignalType.EXCEPTION_CONTRACT_DRIFT, fix=None, description="Bad")
        result = _format_rule(SignalType.EXCEPTION_CONTRACT_DRIFT, [f])
        assert f.title in result

    def test_generic_fallback_with_fix(self):
        f = _finding(signal=SignalType.TEMPORAL_VOLATILITY, fix="Reduce churn")
        result = _format_rule(SignalType.TEMPORAL_VOLATILITY, [f])
        assert "Reduce churn" in result

    def test_generic_fallback_with_desc(self):
        f = _finding(signal=SignalType.TEMPORAL_VOLATILITY, fix=None, description="High volatility")
        result = _format_rule(SignalType.TEMPORAL_VOLATILITY, [f])
        assert "High volatility" in result

    def test_no_file_path_no_top_files(self):
        """Guard clause deficit without file_path → no Priority modules."""
        f = _finding(signal=SignalType.GUARD_CLAUSE_DEFICIT, file_path=None)
        result = _format_rule(SignalType.GUARD_CLAUSE_DEFICIT, [f])
        assert result is not None
        assert "Priority modules" not in result


# ---------------------------------------------------------------------------
# target_default_path
# ---------------------------------------------------------------------------


class TestTargetDefaultPath:
    def test_cursor(self):
        p = target_default_path("cursor", Path("/repo"))
        assert p == Path("/repo/.cursorrules")

    def test_claude(self):
        p = target_default_path("claude", Path("/repo"))
        assert p == Path("/repo/CLAUDE.md")

    def test_copilot_default(self):
        p = target_default_path("copilot", Path("/repo"))
        assert p == Path("/repo/.github/copilot-instructions.md")


# ---------------------------------------------------------------------------
# generate_for_target delegation
# ---------------------------------------------------------------------------


class TestGenerateForTarget:
    def test_cursor_delegation(self):
        a = _analysis()
        result = generate_for_target("cursor", a)
        assert "drift-generated" in result

    def test_claude_delegation(self):
        a = _analysis()
        result = generate_for_target("claude", a)
        assert "drift-generated" in result.lower() or "Drift" in result

    def test_copilot_default(self):
        a = _analysis()
        result = generate_for_target("copilot", a)
        assert MARKER_BEGIN in result


# ---------------------------------------------------------------------------
# generate_instructions
# ---------------------------------------------------------------------------


class TestGenerateInstructions:
    def test_no_findings(self):
        a = _analysis(findings=[])
        result = generate_instructions(a)
        assert "No significant" in result

    def test_with_actionable_findings(self):
        findings = [
            _finding(signal=SignalType.ARCHITECTURE_VIOLATION, file_path="src/a.py", fix="Fix A"),
            _finding(signal=SignalType.ARCHITECTURE_VIOLATION, file_path="src/b.py", fix="Fix B"),
        ]
        a = _analysis(findings=findings)
        result = generate_instructions(a)
        assert "Architectural Constraints" in result
        assert MARKER_BEGIN in result

    def test_with_trend(self):
        findings = [
            _finding(signal=SignalType.ARCHITECTURE_VIOLATION, fix="Fix A"),
            _finding(signal=SignalType.ARCHITECTURE_VIOLATION, fix="Fix B"),
        ]
        trend = TrendContext(
            previous_score=0.2,
            delta=-0.1,
            direction="improving",
            recent_scores=[0.3, 0.2, 0.1],
            history_depth=3,
            transition_ratio=0.0,
        )
        a = _analysis(findings=findings, trend=trend)
        result = generate_instructions(a)
        assert "Trend" in result
        assert "improving" in result

    def test_with_module_scores(self):
        findings = [
            _finding(signal=SignalType.ARCHITECTURE_VIOLATION, fix="Fix A"),
            _finding(signal=SignalType.ARCHITECTURE_VIOLATION, fix="Fix B"),
        ]
        ms = [ModuleScore(path=Path("src/worst"), drift_score=0.9)]
        a = _analysis(findings=findings, module_scores=ms)
        result = generate_instructions(a)
        assert "src/worst" in result


# ---------------------------------------------------------------------------
# generate_cursorrules
# ---------------------------------------------------------------------------


class TestGenerateCursorrules:
    def test_no_findings(self):
        a = _analysis()
        result = generate_cursorrules(a)
        assert "No significant" in result

    def test_with_findings(self):
        findings = [
            _finding(signal=SignalType.ARCHITECTURE_VIOLATION, fix="Fix A"),
            _finding(signal=SignalType.ARCHITECTURE_VIOLATION, fix="Fix B"),
        ]
        a = _analysis(findings=findings)
        result = generate_cursorrules(a)
        assert "[AVS]" in result


# ---------------------------------------------------------------------------
# generate_claude_instructions
# ---------------------------------------------------------------------------


class TestGenerateClaudeInstructions:
    def test_no_findings(self):
        a = _analysis()
        result = generate_claude_instructions(a)
        assert "No significant" in result

    def test_with_findings_and_module_scores(self):
        findings = [
            _finding(signal=SignalType.ARCHITECTURE_VIOLATION, fix="Fix A"),
            _finding(signal=SignalType.ARCHITECTURE_VIOLATION, fix="Fix B"),
        ]
        ms = [ModuleScore(path=Path("src/worst"), drift_score=0.9)]
        a = _analysis(findings=findings, module_scores=ms)
        result = generate_claude_instructions(a)
        assert "Rules" in result
        assert "Hotspots" in result
        assert "src/worst" in result


# ---------------------------------------------------------------------------
# merge_into_file
# ---------------------------------------------------------------------------


class TestMergeIntoFile:
    def test_new_file(self, tmp_path: Path):
        target = tmp_path / "out.md"
        content = "## Instructions\n"
        result = merge_into_file(target, content)
        assert result is True
        assert target.read_text(encoding="utf-8") == content

    def test_replace_between_markers(self, tmp_path: Path):
        target = tmp_path / "out.md"
        original = f"# Header\n{MARKER_BEGIN}\nOLD CONTENT\n{MARKER_END}\n# Footer\n"
        target.write_text(original, encoding="utf-8")
        new_section = f"{MARKER_BEGIN}\nNEW CONTENT\n{MARKER_END}\n"
        result = merge_into_file(target, new_section)
        assert result is True
        text = target.read_text(encoding="utf-8")
        assert "NEW CONTENT" in text
        assert "OLD CONTENT" not in text
        assert "# Header" in text
        assert "# Footer" in text

    def test_append_when_no_markers(self, tmp_path: Path):
        target = tmp_path / "out.md"
        target.write_text("# Existing content\n", encoding="utf-8")
        new_section = "## Drift Section\n"
        result = merge_into_file(target, new_section)
        assert result is True
        text = target.read_text(encoding="utf-8")
        assert "Existing content" in text
        assert "Drift Section" in text

    def test_no_merge_overwrites(self, tmp_path: Path):
        target = tmp_path / "out.md"
        target.write_text("old", encoding="utf-8")
        result = merge_into_file(target, "new", no_merge=True)
        assert result is True
        assert target.read_text(encoding="utf-8") == "new"

    def test_unchanged_content_not_written(self, tmp_path: Path):
        target = tmp_path / "out.md"
        existing = f"# H\n{MARKER_BEGIN}\nX\n{MARKER_END}\n"
        target.write_text(existing, encoding="utf-8")
        marker_content = f"{MARKER_BEGIN}\nX\n{MARKER_END}\n"
        result = merge_into_file(target, marker_content)
        assert result is False

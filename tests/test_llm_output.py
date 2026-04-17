"""Unit tests for LLM/AI-agent output formatter."""

from __future__ import annotations

import datetime
from pathlib import Path

from drift.models import Finding, ModuleScore, RepoAnalysis, Severity, SignalType
from drift.output.llm_output import analysis_to_llm


def _sample_analysis(findings: list[Finding] | None = None) -> RepoAnalysis:
    if findings is None:
        findings = [
            Finding(
                signal_type=SignalType.PATTERN_FRAGMENTATION,
                severity=Severity.HIGH,
                score=0.85,
                title="Error handling split 4 ways",
                description="Multiple divergent patterns detected.",
                file_path=Path("src/api/routes.py"),
                start_line=42,
                end_line=58,
                impact=0.9,
            ),
            Finding(
                signal_type=SignalType.SYSTEM_MISALIGNMENT,
                severity=Severity.MEDIUM,
                score=0.5,
                title="Config drift",
                description="Environment handling differs.",
                file_path=Path("src/config.py"),
                start_line=10,
                end_line=20,
                impact=0.1,
            ),
        ]
    module = ModuleScore(
        path=Path("src/api"),
        drift_score=0.73,
        signal_scores={SignalType.PATTERN_FRAGMENTATION: 0.73},
        findings=findings,
        ai_ratio=0.0,
    )
    return RepoAnalysis(
        repo_path=Path("my-repo"),
        analyzed_at=datetime.datetime(2026, 1, 2, 10, 30, tzinfo=datetime.UTC),
        drift_score=0.73,
        module_scores=[module],
        findings=findings,
        total_files=12,
        total_functions=48,
        ai_attributed_ratio=0.25,
        analysis_duration_seconds=2.3,
    )


def test_llm_no_ansi_escape_codes() -> None:
    output = analysis_to_llm(_sample_analysis())
    assert "\033[" not in output
    assert "\x1b[" not in output


def test_llm_header_contains_version_and_repo() -> None:
    output = analysis_to_llm(_sample_analysis())
    first_line = output.split("\n")[0]
    assert "drift" in first_line
    assert "my-repo" in first_line


def test_llm_footer_statistics() -> None:
    output = analysis_to_llm(_sample_analysis())
    last_line = output.strip().split("\n")[-1]
    assert "2 findings" in last_line
    assert "1 high" in last_line
    assert "1 medium" in last_line
    assert "score:" in last_line


def test_llm_one_line_per_finding() -> None:
    output = analysis_to_llm(_sample_analysis())
    lines = output.strip().split("\n")
    # header + 2 findings + footer = 4 lines
    assert len(lines) == 4


def test_llm_finding_format() -> None:
    output = analysis_to_llm(_sample_analysis())
    lines = output.strip().split("\n")
    # Second line = first finding
    assert lines[1].startswith("[PFS:HIGH]")
    assert "src/api/routes.py:42" in lines[1]
    assert "Error handling split 4 ways" in lines[1]


def test_llm_empty_findings() -> None:
    analysis = _sample_analysis(findings=[])
    output = analysis_to_llm(analysis)
    lines = output.strip().split("\n")
    # header + footer = 2 lines
    assert len(lines) == 2
    assert "0 findings" in lines[-1]


def test_llm_token_efficiency() -> None:
    """Each finding should be compact — regression guard."""
    output = analysis_to_llm(_sample_analysis())
    lines = output.strip().split("\n")
    finding_lines = lines[1:-1]  # exclude header and footer
    for line in finding_lines:
        # Each finding line should be under 200 chars
        assert len(line) < 200, f"Finding line too long ({len(line)} chars): {line}"


def test_llm_respects_max_findings_and_reports_omitted() -> None:
    findings = [
        Finding(
            signal_type=SignalType.SYSTEM_MISALIGNMENT,
            severity=Severity.MEDIUM,
            score=0.3,
            title="Medium first",
            description="medium",
            file_path=Path("src/medium.py"),
            start_line=11,
            end_line=12,
            impact=0.9,
        ),
        Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.HIGH,
            score=0.7,
            title="High lower impact",
            description="high",
            file_path=Path("src/high_b.py"),
            start_line=21,
            end_line=22,
            impact=0.2,
        ),
        Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.HIGH,
            score=0.8,
            title="High higher impact",
            description="high",
            file_path=Path("src/high_a.py"),
            start_line=31,
            end_line=32,
            impact=0.8,
        ),
    ]

    output = analysis_to_llm(_sample_analysis(findings=findings), max_findings=2)
    lines = output.strip().split("\n")

    # header + 2 findings + omitted + footer
    assert len(lines) == 5
    assert "High higher impact" in lines[1]
    assert "High lower impact" in lines[2]
    assert "(+1 more findings omitted - re-run with --max-findings to adjust)" in lines[3]
    assert "3 findings" in lines[-1]

"""Unit tests for CSV output serialization."""

from __future__ import annotations

import csv
import datetime
import io
from pathlib import Path

from drift.models import Finding, ModuleScore, RepoAnalysis, Severity, SignalType
from drift.output.csv_output import analysis_to_csv


def _sample_analysis() -> RepoAnalysis:
    finding_one = Finding(
        signal_type=SignalType.PATTERN_FRAGMENTATION,
        severity=Severity.HIGH,
        score=0.85,
        title="Error handling split 4 ways",
        description="Multiple divergent patterns detected.",
        file_path=Path("src/api/routes.py"),
        start_line=42,
        end_line=58,
        impact=0.9,
    )
    finding_two = Finding(
        signal_type=SignalType.SYSTEM_MISALIGNMENT,
        severity=Severity.MEDIUM,
        score=0.5,
        title="Config drift",
        description="Environment handling differs.",
        file_path=None,
        start_line=None,
        end_line=None,
        impact=0.1,
    )

    module = ModuleScore(
        path=Path("src/api"),
        drift_score=0.73,
        signal_scores={SignalType.PATTERN_FRAGMENTATION: 0.73},
        findings=[finding_one, finding_two],
        ai_ratio=0.0,
    )
    return RepoAnalysis(
        repo_path=Path("."),
        analyzed_at=datetime.datetime(2026, 1, 2, 10, 30, tzinfo=datetime.UTC),
        drift_score=0.73,
        module_scores=[module],
        findings=[finding_two, finding_one],
        total_files=12,
        total_functions=48,
        ai_attributed_ratio=0.25,
        analysis_duration_seconds=2.3,
    )


def test_analysis_to_csv_contains_header_and_rows() -> None:
    rendered = analysis_to_csv(_sample_analysis())
    rows = list(csv.reader(io.StringIO(rendered)))

    assert rows[0] == ["signal", "severity", "score", "title", "file", "start_line", "end_line"]
    assert rows[1] == [
        "PFS",
        "high",
        "0.85",
        "Error handling split 4 ways",
        "src/api/routes.py",
        "42",
        "58",
    ]
    assert rows[2] == ["SMS", "medium", "0.5", "Config drift", "", "", ""]


def test_analysis_to_csv_escapes_commas_and_quotes() -> None:
    finding = Finding(
        signal_type=SignalType.PATTERN_FRAGMENTATION,
        severity=Severity.HIGH,
        score=0.4,
        title='Title with "quote", and comma',
        description="desc",
        file_path=Path("src/a.py"),
        start_line=1,
        end_line=2,
        impact=0.2,
    )
    analysis = _sample_analysis()
    analysis.findings = [finding]

    rendered = analysis_to_csv(analysis)
    rows = list(csv.reader(io.StringIO(rendered)))

    assert rows[1][3] == 'Title with "quote", and comma'
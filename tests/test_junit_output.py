"""Unit tests for JUnit XML output formatter."""

from __future__ import annotations

import datetime
import xml.etree.ElementTree as ET
from pathlib import Path

from drift.models import Finding, ModuleScore, RepoAnalysis, Severity, SignalType
from drift.output.junit_output import analysis_to_junit


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
                file_path=None,
                start_line=None,
                end_line=None,
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
        repo_path=Path("."),
        analyzed_at=datetime.datetime(2026, 1, 2, 10, 30, tzinfo=datetime.UTC),
        drift_score=0.73,
        module_scores=[module],
        findings=findings,
        total_files=12,
        total_functions=48,
        ai_attributed_ratio=0.25,
        analysis_duration_seconds=2.3,
    )


def test_junit_valid_xml() -> None:
    xml_str = analysis_to_junit(_sample_analysis())
    root = ET.fromstring(xml_str)
    assert root.tag == "testsuites"


def test_junit_testsuite_attributes() -> None:
    xml_str = analysis_to_junit(_sample_analysis())
    root = ET.fromstring(xml_str)
    suite = root.find("testsuite")
    assert suite is not None
    assert suite.get("name") == "drift"
    assert suite.get("tests") == "2"
    assert suite.get("failures") == "2"
    assert suite.get("errors") == "0"


def test_junit_testcase_per_finding() -> None:
    xml_str = analysis_to_junit(_sample_analysis())
    root = ET.fromstring(xml_str)
    suite = root.find("testsuite")
    assert suite is not None
    testcases = suite.findall("testcase")
    assert len(testcases) == 2

    # First finding
    tc0 = testcases[0]
    assert tc0.get("classname") == "PFS"
    assert tc0.get("name") == "src/api/routes.py:42"
    failure = tc0.find("failure")
    assert failure is not None
    assert failure.get("message") == "Error handling split 4 ways"
    assert failure.get("type") == "high"


def test_junit_empty_findings() -> None:
    analysis = _sample_analysis(findings=[])
    xml_str = analysis_to_junit(analysis)
    root = ET.fromstring(xml_str)
    suite = root.find("testsuite")
    assert suite is not None
    assert suite.get("tests") == "1"
    assert suite.get("failures") == "0"
    testcases = suite.findall("testcase")
    assert len(testcases) == 1
    assert testcases[0].get("name") == "no-findings"
    assert testcases[0].find("failure") is None


def test_junit_xml_escaping() -> None:
    findings = [
        Finding(
            signal_type=SignalType.PATTERN_FRAGMENTATION,
            severity=Severity.HIGH,
            score=0.8,
            title='Error in <module> & "config"',
            description="Uses <unsafe> & 'patterns'",
            file_path=Path("src/test.py"),
            start_line=1,
            impact=0.5,
        ),
    ]
    xml_str = analysis_to_junit(_sample_analysis(findings=findings))
    # Must parse without error — proves escaping works
    root = ET.fromstring(xml_str)
    tc = root.find(".//testcase")
    assert tc is not None
    failure = tc.find("failure")
    assert failure is not None
    assert "<module>" in (failure.get("message") or "")

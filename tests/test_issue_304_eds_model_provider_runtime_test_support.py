from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context, is_test_file
from drift.models import FunctionInfo, ParseResult, Severity
from drift.signals.explainability_deficit import ExplainabilityDeficitSignal

ISSUE_304_FILE = Path("src/agents/pi-embedded-runner/model.provider-runtime.test-support.ts")


def _make_fn(*, file_path: Path) -> FunctionInfo:
    return FunctionInfo(
        name="createProviderRuntimeTestMock",
        file_path=file_path,
        start_line=416,
        end_line=547,
        language="typescript",
        complexity=62,
        loc=132,
        parameters=["options", "provider", "runtime"],
        return_type=None,
        decorators=[],
        has_docstring=False,
        is_exported=True,
    )


def test_issue_304_model_provider_runtime_test_support_is_test_context() -> None:
    assert is_test_file(ISSUE_304_FILE)
    assert classify_file_context(ISSUE_304_FILE) == "test"


def test_issue_304_eds_reduce_severity_marks_test_context() -> None:
    parse_result = ParseResult(
        file_path=ISSUE_304_FILE,
        language="typescript",
        functions=[_make_fn(file_path=ISSUE_304_FILE)],
    )

    findings = ExplainabilityDeficitSignal().analyze(
        [parse_result],
        {},
        DriftConfig(test_file_handling="reduce_severity"),
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.metadata.get("finding_context") == "test"
    assert finding.finding_context == "test"
    assert finding.severity == Severity.LOW


def test_issue_304_eds_exclude_suppresses_test_context() -> None:
    parse_result = ParseResult(
        file_path=ISSUE_304_FILE,
        language="typescript",
        functions=[_make_fn(file_path=ISSUE_304_FILE)],
    )

    findings = ExplainabilityDeficitSignal().analyze(
        [parse_result],
        {},
        DriftConfig(test_file_handling="exclude"),
    )

    assert findings == []

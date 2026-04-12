from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context, is_test_file
from drift.models import FunctionInfo, ParseResult, Severity
from drift.signals.explainability_deficit import ExplainabilityDeficitSignal


def _make_fn(
    *,
    file_path: Path,
    name: str,
    start_line: int,
    end_line: int,
    complexity: int,
    loc: int,
) -> FunctionInfo:
    return FunctionInfo(
        name=name,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        language="typescript",
        complexity=complexity,
        loc=loc,
        parameters=["input", "body"],
        return_type=None,
        decorators=[],
        has_docstring=False,
        is_exported=False,
    )


def _parse_result(file_path: Path) -> ParseResult:
    return ParseResult(
        file_path=file_path,
        language="typescript",
        functions=[
            _make_fn(
                file_path=file_path,
                name="normalizeDynamicModel",
                start_line=67,
                end_line=85,
                complexity=12,
                loc=19,
            ),
            _make_fn(
                file_path=file_path,
                name="buildDynamicModel",
                start_line=123,
                end_line=414,
                complexity=40,
                loc=292,
            ),
            _make_fn(
                file_path=file_path,
                name="createProviderRuntimeTestMock",
                start_line=416,
                end_line=547,
                complexity=18,
                loc=132,
            ),
        ],
    )


def test_issue_321_model_provider_runtime_test_support_is_test_context() -> None:
    relative = Path("src/agents/pi-embedded-runner/model.provider-runtime.test-support.ts")
    absolute = Path(
        "C:/tmp/openclaw/src/agents/pi-embedded-runner/model.provider-runtime.test-support.ts"
    )

    assert is_test_file(relative)
    assert classify_file_context(relative) == "test"
    assert is_test_file(absolute)
    assert classify_file_context(absolute) == "test"


def test_issue_321_eds_reduce_severity_marks_test_context() -> None:
    file_path = Path("src/agents/pi-embedded-runner/model.provider-runtime.test-support.ts")
    parse_result = _parse_result(file_path)

    findings = ExplainabilityDeficitSignal().analyze(
        [parse_result],
        {},
        DriftConfig(test_file_handling="reduce_severity"),
    )

    assert findings
    for finding in findings:
        assert finding.file_path == file_path
        assert finding.metadata.get("finding_context") == "test"
        assert finding.finding_context == "test"
        assert finding.severity == Severity.LOW


def test_issue_321_eds_exclude_suppresses_test_context_findings() -> None:
    file_path = Path("src/agents/pi-embedded-runner/model.provider-runtime.test-support.ts")
    parse_result = _parse_result(file_path)

    findings = ExplainabilityDeficitSignal().analyze(
        [parse_result],
        {},
        DriftConfig(test_file_handling="exclude"),
    )

    assert findings == []

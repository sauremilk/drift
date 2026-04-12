from __future__ import annotations

from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context, is_test_file
from drift.models import FunctionInfo, ParseResult
from drift.signals.explainability_deficit import ExplainabilityDeficitSignal

ISSUE_306_FILE = Path(
    "src/agents/pi-embedded-runner/run/attempt.spawn-workspace.test-support.ts"
)


def _make_fn(*, file_path: Path) -> FunctionInfo:
    return FunctionInfo(
        name="createContextEngineAttemptRunner",
        file_path=file_path,
        start_line=810,
        end_line=948,
        language="typescript",
        complexity=10,
        loc=139,
        parameters=["params"],
        return_type=None,
        decorators=[],
        has_docstring=False,
        is_exported=True,
    )


def test_issue_306_attempt_spawn_workspace_test_support_is_test_context() -> None:
    assert is_test_file(ISSUE_306_FILE)
    assert classify_file_context(ISSUE_306_FILE) == "test"


def test_issue_306_eds_reduce_severity_suppresses_false_positive() -> None:
    parse_result = ParseResult(
        file_path=ISSUE_306_FILE,
        language="typescript",
        functions=[_make_fn(file_path=ISSUE_306_FILE)],
    )

    findings = ExplainabilityDeficitSignal().analyze(
        [parse_result],
        {},
        DriftConfig(test_file_handling="reduce_severity"),
    )

    assert findings == []


def test_issue_306_eds_exclude_suppresses_test_context() -> None:
    parse_result = ParseResult(
        file_path=ISSUE_306_FILE,
        language="typescript",
        functions=[_make_fn(file_path=ISSUE_306_FILE)],
    )

    findings = ExplainabilityDeficitSignal().analyze(
        [parse_result],
        {},
        DriftConfig(test_file_handling="exclude"),
    )

    assert findings == []
"""Crash-guard tests for all signal detectors.

Each signal's ``analyze()`` method must:
1. Never raise an unexpected exception on any well-formed or pathological input.
2. Always return a ``list[Finding]``.
3. Only produce findings with scores in [0.0, 1.0].

These are property-style boundary tests covering the most common bug classes
observed in the risk register: IndexError, ZeroDivisionError, AttributeError,
and KeyError on edge-case ASTs.

The parametrize list auto-discovers signals from the registry after importing
every signal module, so new signals are covered automatically.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

import drift.signals  # noqa: F401 – triggers subpackage traversal

# ---------------------------------------------------------------------------
# Auto-import all signal modules so that @register_signal decorators run.
# ---------------------------------------------------------------------------
import drift.signals.architecture_violation  # noqa: F401  # noqa: F401
import drift.signals.broad_exception_monoculture  # noqa: F401  # noqa: F401
import drift.signals.bypass_accumulation  # noqa: F401  # noqa: F401
import drift.signals.circular_import  # noqa: F401  # noqa: F401
import drift.signals.co_change_coupling  # noqa: F401  # noqa: F401
import drift.signals.cognitive_complexity  # noqa: F401  # noqa: F401
import drift.signals.cohesion_deficit  # noqa: F401  # noqa: F401
import drift.signals.dead_code_accumulation  # noqa: F401  # noqa: F401
import drift.signals.doc_impl_drift  # noqa: F401  # noqa: F401
import drift.signals.exception_contract_drift  # noqa: F401  # noqa: F401
import drift.signals.explainability_deficit  # noqa: F401  # noqa: F401
import drift.signals.fan_out_explosion  # noqa: F401  # noqa: F401
import drift.signals.guard_clause_deficit  # noqa: F401  # noqa: F401
import drift.signals.hardcoded_secret  # noqa: F401  # noqa: F401
import drift.signals.insecure_default  # noqa: F401  # noqa: F401
import drift.signals.missing_authorization  # noqa: F401  # noqa: F401
import drift.signals.mutant_duplicates  # noqa: F401  # noqa: F401
import drift.signals.naming_contract_violation  # noqa: F401  # noqa: F401
import drift.signals.pattern_fragmentation  # noqa: F401  # noqa: F401
import drift.signals.system_misalignment  # noqa: F401  # noqa: F401
import drift.signals.temporal_volatility  # noqa: F401  # noqa: F401
import drift.signals.test_polarity_deficit  # noqa: F401  # noqa: F401
import drift.signals.ts_architecture  # noqa: F401  # noqa: F401
from drift.config import DriftConfig
from drift.models import (
    ClassInfo,
    FileHistory,
    Finding,
    FunctionInfo,
    ImportInfo,
    ParseResult,
)
from drift.signals import base as signal_base

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONFIG = DriftConfig(
    include=["**/*.py"],
    exclude=["**/__pycache__/**"],
    embeddings_enabled=False,
)

_NOW = datetime.datetime.now(tz=datetime.UTC)
_OLD = _NOW - datetime.timedelta(days=120)


def _make_file_history(path: Path, *, commits: int = 5) -> FileHistory:
    return FileHistory(
        path=path,
        total_commits=commits,
        unique_authors=1,
        ai_attributed_commits=0,
        change_frequency_30d=0.5,
        defect_correlated_commits=0,
        last_modified=_OLD,
        first_seen=_OLD,
    )


def _make_parse_result(
    file_path: Path,
    *,
    functions: list[FunctionInfo] | None = None,
    classes: list[ClassInfo] | None = None,
    imports: list[ImportInfo] | None = None,
    line_count: int = 10,
    parse_errors: list[str] | None = None,
) -> ParseResult:
    return ParseResult(
        file_path=file_path,
        language="python",
        functions=functions or [],
        classes=classes or [],
        imports=imports or [],
        line_count=line_count,
        parse_errors=parse_errors or [],
    )


# ---------------------------------------------------------------------------
# Pathological input scenarios
# ---------------------------------------------------------------------------

_EMPTY_PARSE_RESULTS: list[ParseResult] = []
_EMPTY_FILE_HISTORIES: dict[str, FileHistory] = {}


def _single_empty_file(tmp_path: Path) -> tuple[list[ParseResult], dict[str, FileHistory]]:
    """One file, zero functions, zero imports."""
    fp = tmp_path / "empty.py"
    fp.write_text("")
    pr = _make_parse_result(fp, line_count=0)
    fh = {fp.as_posix(): _make_file_history(fp, commits=1)}
    return [pr], fh


def _minimal_function_file(tmp_path: Path) -> tuple[list[ParseResult], dict[str, FileHistory]]:
    """One file with a single minimal function."""
    fp = tmp_path / "minimal.py"
    fp.write_text("def f(): pass\n")
    func = FunctionInfo(
        name="f",
        file_path=fp,
        start_line=1,
        end_line=1,
        language="python",
        complexity=1,
        loc=1,
    )
    pr = _make_parse_result(fp, functions=[func], line_count=2)
    fh = {fp.as_posix(): _make_file_history(fp)}
    return [pr], fh


def _parse_error_file(tmp_path: Path) -> tuple[list[ParseResult], dict[str, FileHistory]]:
    """File where parsing produced errors (simulated broken syntax)."""
    fp = tmp_path / "broken.py"
    fp.write_text("def \n")
    pr = _make_parse_result(
        fp,
        line_count=1,
        parse_errors=["SyntaxError: invalid syntax at line 1"],
    )
    fh = {fp.as_posix(): _make_file_history(fp)}
    return [pr], fh


def _many_identical_functions(tmp_path: Path) -> tuple[list[ParseResult], dict[str, FileHistory]]:
    """Many identical functions — exercises duplicate-detection edge cases."""
    fp = tmp_path / "dup.py"
    lines = "\n".join(f"def f{i}(): pass" for i in range(50))
    fp.write_text(lines)
    functions = [
        FunctionInfo(
            name=f"f{i}",
            file_path=fp,
            start_line=i + 1,
            end_line=i + 1,
            language="python",
            body_hash="deadbeef",  # identical hash → duplicate candidate
            loc=1,
        )
        for i in range(50)
    ]
    pr = _make_parse_result(fp, functions=functions, line_count=50)
    fh = {fp.as_posix(): _make_file_history(fp, commits=10)}
    return [pr], fh


def _zero_commit_history(tmp_path: Path) -> tuple[list[ParseResult], dict[str, FileHistory]]:
    """File history with zero commits (division-by-zero candidate)."""
    fp = tmp_path / "new.py"
    fp.write_text("def new(): pass\n")
    func = FunctionInfo(
        name="new",
        file_path=fp,
        start_line=1,
        end_line=1,
        language="python",
        loc=1,
    )
    pr = _make_parse_result(fp, functions=[func], line_count=2)
    fh = {fp.as_posix(): _make_file_history(fp, commits=0)}
    return [pr], fh


def _large_file(tmp_path: Path) -> tuple[list[ParseResult], dict[str, FileHistory]]:
    """File with many functions (stress-test performance guards)."""
    fp = tmp_path / "large.py"
    n = 200
    fp.write_text("\n".join(f"def func_{i}(x, y): return x + y" for i in range(n)))
    functions = [
        FunctionInfo(
            name=f"func_{i}",
            file_path=fp,
            start_line=i + 1,
            end_line=i + 1,
            language="python",
            complexity=1,
            loc=1,
            has_docstring=False,
        )
        for i in range(n)
    ]
    pr = _make_parse_result(fp, functions=functions, line_count=n)
    fh = {fp.as_posix(): _make_file_history(fp, commits=50)}
    return [pr], fh


# ---------------------------------------------------------------------------
# Parametrize: signal classes × input scenarios
# ---------------------------------------------------------------------------

_SIGNAL_CLASSES = list(signal_base._SIGNAL_REGISTRY)

_SCENARIO_IDS = [
    "empty_results",
    "single_empty_file",
    "minimal_function",
    "parse_error_file",
    "many_identical_functions",
    "zero_commit_history",
    "large_file",
]


def _build_scenarios(
    tmp_path: Path,
) -> list[tuple[list[ParseResult], dict[str, FileHistory]]]:
    return [
        (_EMPTY_PARSE_RESULTS, _EMPTY_FILE_HISTORIES),
        _single_empty_file(tmp_path),
        _minimal_function_file(tmp_path),
        _parse_error_file(tmp_path),
        _many_identical_functions(tmp_path),
        _zero_commit_history(tmp_path),
        _large_file(tmp_path),
    ]


@pytest.mark.parametrize("signal_cls", _SIGNAL_CLASSES, ids=[s.__name__ for s in _SIGNAL_CLASSES])
@pytest.mark.parametrize("scenario_id", _SCENARIO_IDS)
def test_signal_does_not_crash(
    signal_cls: type[signal_base.BaseSignal],
    scenario_id: str,
    tmp_path: Path,
) -> None:
    """Signal must return list[Finding] without crashing on any scenario."""
    scenarios = _build_scenarios(tmp_path)
    idx = _SCENARIO_IDS.index(scenario_id)
    parse_results, file_histories = scenarios[idx]

    signal = signal_cls()
    signal.bind_context(
        signal_base.SignalCapabilities(
            repo_path=tmp_path,
            embedding_service=None,
            commits=[],
        )
    )

    result = signal.analyze(parse_results, file_histories, _CONFIG)

    assert isinstance(result, list), (
        f"{signal_cls.__name__}.analyze() must return list, got {type(result)}"
    )
    for finding in result:
        assert isinstance(finding, Finding), (
            f"{signal_cls.__name__} returned non-Finding in list: {type(finding)}"
        )
        assert 0.0 <= finding.score <= 1.0, (
            f"{signal_cls.__name__} produced out-of-bounds score {finding.score} "
            f"in scenario '{scenario_id}'"
        )

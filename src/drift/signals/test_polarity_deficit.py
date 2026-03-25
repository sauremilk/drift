"""Signal 9: Test Polarity Deficit (TPD).

Detects test suites that overwhelmingly test the happy path without
exercising negative / edge-case / boundary conditions — a structural
proxy for test suites that *look* comprehensive but leave semantic gaps.

Epistemics: Cannot detect WHICH edge-cases are missing, but CAN detect
the structural pattern of uniform positive-only testing that correlates
with hidden defect classes.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    ParseResult,
    SignalType,
    severity_for_score,
)
from drift.signals.base import BaseSignal, register_signal

# Assertion call names considered "negative" (error-path / edge-case testing)
_NEGATIVE_CALLS: frozenset[str] = frozenset({
    "assertRaises",
    "assertRaisesRegex",
    "assertWarns",
    "assertWarnsRegex",
    "assertFalse",
    "assertNotIn",
    "assertNotEqual",
    "assertNotIsInstance",
    "assertIsNone",
    "assertNotRegex",
})

# Attribute-based negative calls (e.g. pytest.raises, self.assertRaises)
_NEGATIVE_ATTRS: frozenset[str] = frozenset({
    "raises",        # pytest.raises
    "warns",         # pytest.warns
    "assertRaises",
    "assertRaisesRegex",
    "assertFalse",
    "assertNotIn",
    "assertNotEqual",
    "assertNotIsInstance",
    "assertIsNone",
})

# Keywords in test function names indicating boundary/edge testing
_BOUNDARY_KEYWORDS: frozenset[str] = frozenset({
    "boundary", "edge", "limit", "zero", "empty", "null", "none",
    "negative", "invalid", "error", "fail", "overflow", "underflow",
    "missing", "corrupt", "malformed", "bad", "wrong",
})


def _is_test_file(file_path: Path) -> bool:
    """Heuristic: is this a test file?"""
    name = file_path.name.lower()
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.tsx")
    )


class _AssertionCounter(ast.NodeVisitor):
    """Walk an AST and count positive vs. negative assertions."""

    def __init__(self) -> None:
        self.positive = 0
        self.negative = 0

    def visit_Assert(self, node: ast.Assert) -> None:  # noqa: N802
        # Plain `assert` — positive by default
        self.positive += 1
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:  # noqa: N802
        for item in node.items:
            ctx = item.context_expr
            if isinstance(ctx, ast.Call):
                self._check_call(ctx)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        self._check_call(node)
        self.generic_visit(node)

    def _check_call(self, node: ast.Call) -> None:
        func = node.func
        name: str | None = None
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id

        if name is None:
            return

        if name in _NEGATIVE_CALLS or name in _NEGATIVE_ATTRS:
            self.negative += 1
        elif name.startswith("assert"):
            # Any other assert* call is positive
            self.positive += 1


def _has_boundary_name(func_name: str) -> bool:
    """Return True if the function name suggests boundary/edge testing."""
    lower = func_name.lower()
    return any(kw in lower for kw in _BOUNDARY_KEYWORDS)


def _count_test_functions(source: str) -> tuple[int, list[str]]:
    """Count test functions and return their names."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0, []

    names: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and (node.name.startswith("test_") or node.name.startswith("test"))
        ):
            names.append(node.name)
    return len(names), names


@register_signal
class TestPolarityDeficitSignal(BaseSignal):
    """Detect test suites dominated by happy-path-only assertions."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.TEST_POLARITY_DEFICIT

    @property
    def name(self) -> str:
        return "Test Polarity Deficit"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        min_test_fns = config.thresholds.tpd_min_test_functions

        # Group test file data by module
        module_data: dict[Path, dict] = defaultdict(
            lambda: {
                "positive": 0,
                "negative": 0,
                "test_functions": 0,
                "boundary_functions": 0,
                "files": [],
                "function_names": [],
            }
        )

        for pr in parse_results:
            if pr.language != "python":
                continue
            if not _is_test_file(pr.file_path):
                continue

            # Read source for AST-based assertion counting
            try:
                source = pr.file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            counter = _AssertionCounter()
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            counter.visit(tree)

            fn_count, fn_names = _count_test_functions(source)

            module = pr.file_path.parent
            data = module_data[module]
            data["positive"] += counter.positive
            data["negative"] += counter.negative
            data["test_functions"] += fn_count
            data["function_names"].extend(fn_names)
            data["files"].append(pr.file_path)

            # Count boundary-named functions as contributing to negative
            for name in fn_names:
                if _has_boundary_name(name):
                    data["boundary_functions"] += 1

        findings: list[Finding] = []

        for module, data in module_data.items():
            total_fns = data["test_functions"]
            if total_fns < min_test_fns:
                continue

            positive = data["positive"]
            negative = data["negative"] + data["boundary_functions"]
            total_assertions = positive + negative
            if total_assertions < 10:
                continue

            negative_ratio = negative / total_assertions

            if negative_ratio >= 0.10:
                continue

            # Score: penalise lack of negative tests, scaled by suite size
            suite_factor = min(1.0, total_fns / 10)
            score = min(1.0, (1.0 - negative_ratio) * suite_factor)
            severity = severity_for_score(score)
            files = sorted(data["files"])

            findings.append(
                Finding(
                    signal_type=SignalType.TEST_POLARITY_DEFICIT,
                    severity=severity,
                    score=score,
                    title=f"Test-Polaritätsdefizit: {module}",
                    description=(
                        f"{total_fns} Testfunktionen mit "
                        f"{positive} positiven und "
                        f"{negative} negativen Assertions "
                        f"(Negativ-Ratio: {negative_ratio:.1%}). "
                        f"Test-Suite prüft fast ausschließlich den Happy-Path."
                    ),
                    file_path=files[0] if files else None,
                    related_files=files[1:],
                    fix=(
                        f"Modul {module.name}: Ergänze pytest.raises / "
                        f"assertRaises Tests für Fehlerfälle und "
                        f"Boundary-Conditions."
                    ),
                    metadata={
                        "test_functions": total_fns,
                        "positive_assertions": positive,
                        "negative_assertions": negative,
                        "boundary_functions": data["boundary_functions"],
                        "negative_ratio": negative_ratio,
                    },
                )
            )

        return findings

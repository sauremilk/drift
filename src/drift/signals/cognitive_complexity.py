"""Signal: Cognitive Complexity (CXS).

Detects functions whose cognitive complexity exceeds a configurable
threshold, indicating hard-to-understand control flow.

The metric follows the SonarSource cognitive-complexity model:
increments for each break in linear flow (if, for, while, except, …)
with a nesting bonus that penalises deeply nested structures more
heavily than equivalent flat code.

Deterministic, AST-only, LLM-free.
"""

from __future__ import annotations

import ast
from pathlib import Path

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    FunctionInfo,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals._utils import _SUPPORTED_LANGUAGES, is_test_file
from drift.signals.base import BaseSignal, register_signal

# ---------------------------------------------------------------------------
# Cognitive-complexity calculation (SonarSource-style)
# ---------------------------------------------------------------------------

# Statements that increment complexity and increase nesting.
_NESTING_INCREMENTS: frozenset[type] = frozenset({
    ast.If,
    ast.For,
    ast.While,
    ast.AsyncFor,
    ast.AsyncWith,
    ast.With,
    ast.ExceptHandler,
})

# Statements that increment complexity but do NOT increase nesting.
_FLAT_INCREMENTS: frozenset[type] = frozenset({
    ast.BoolOp,
})


def _cognitive_complexity_of_body(
    stmts: list[ast.stmt],
    nesting: int = 0,
) -> int:
    """Recursively compute cognitive complexity for a list of statements."""
    total = 0
    for stmt in stmts:
        if isinstance(stmt, tuple(_NESTING_INCREMENTS)):
            # +1 inherent increment + nesting bonus
            total += 1 + nesting
            # recurse into children with increased nesting
            total += _complexity_children(stmt, nesting + 1)
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # nested function — increase nesting but no inherent increment
            total += _cognitive_complexity_of_body(stmt.body, nesting + 1)
        else:
            total += _complexity_children(stmt, nesting)

        # boolean operators within expressions
        total += _count_bool_ops(stmt)

    return total


def _complexity_children(node: ast.stmt, nesting: int) -> int:
    """Sum cognitive complexity of all child statement blocks."""
    total = 0
    for attr in ("body", "orelse", "finalbody", "handlers"):
        children = getattr(node, attr, None)
        if children is None:
            continue
        if isinstance(children, list):
            # `handlers` contains ExceptHandler nodes
            total += _cognitive_complexity_of_body(children, nesting)
    return total


def _count_bool_ops(node: ast.AST) -> int:
    """Count boolean-operator sequences (&&/||) as +1 each."""
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.BoolOp):
            # Each BoolOp chain of same type = +1 (not per operand)
            count += 1
    # Subtract 1 if the node itself is a BoolOp (already counted by walk)
    if isinstance(node, ast.BoolOp):
        count -= 1
    return count


def _function_cognitive_complexity(source: str, func: FunctionInfo) -> int | None:
    """Extract cognitive complexity for a single function from source."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return _cognitive_complexity_of_body(node.body)
    return None


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------


@register_signal
class CognitiveComplexitySignal(BaseSignal):
    """Detect functions with excessive cognitive complexity."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.COGNITIVE_COMPLEXITY

    @property
    def name(self) -> str:
        return "Cognitive Complexity"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        threshold = config.thresholds.cxs_max_complexity
        findings: list[Finding] = []

        for pr in parse_results:
            if pr.language not in _SUPPORTED_LANGUAGES:
                continue
            # Skip TS/JS for now — Python only (AST-based)
            if pr.language != "python":
                continue
            if is_test_file(pr.file_path):
                continue

            source = self._read_source(pr.file_path)
            if source is None:
                continue

            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                # Skip private helpers and trivial functions
                if node.name.startswith("_"):
                    continue
                body_lines = (node.end_lineno or node.lineno) - node.lineno + 1
                if body_lines < 5:
                    continue

                cc = _cognitive_complexity_of_body(node.body)
                if cc <= threshold:
                    continue

                overshoot = cc - threshold
                score = round(min(1.0, 0.3 + overshoot * 0.04), 3)
                severity = Severity.HIGH if score >= 0.7 else Severity.MEDIUM

                findings.append(
                    Finding(
                        signal_type=self.signal_type,
                        severity=severity,
                        score=score,
                        title=f"High cognitive complexity in {node.name}()",
                        description=(
                            f"Function '{node.name}' in {pr.file_path} has "
                            f"cognitive complexity {cc} (threshold: {threshold}). "
                            f"Complex control flow makes this function hard to "
                            f"understand and maintain."
                        ),
                        file_path=pr.file_path,
                        start_line=node.lineno,
                        end_line=node.end_lineno,
                        fix=(
                            f"Reduce cognitive complexity of '{node.name}' "
                            f"(currently {cc}, threshold {threshold}): "
                            f"extract nested logic into helper functions, "
                            f"replace nested conditionals with guard clauses, "
                            f"simplify boolean expressions."
                        ),
                        metadata={
                            "cognitive_complexity": cc,
                            "threshold": threshold,
                            "function_name": node.name,
                            "body_lines": body_lines,
                        },
                        rule_id="cognitive_complexity",
                    )
                )

        return findings

    def _read_source(self, file_path: Path) -> str | None:
        try:
            target = file_path
            if self._repo_path and not file_path.is_absolute():
                target = self._repo_path / file_path
            return target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

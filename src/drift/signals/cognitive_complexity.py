"""Signal: Cognitive Complexity (CXS).

Detects functions whose cognitive complexity exceeds a configurable
threshold, indicating hard-to-understand control flow.

The metric follows the SonarSource cognitive-complexity model:
increments for each break in linear flow (if, for, while, except, …)
with a nesting bonus that penalises deeply nested structures more
heavily than equivalent flat code.

Supports Python (via ``ast``) and TypeScript/JavaScript (via
``tree-sitter``).

Deterministic, AST-only, LLM-free.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

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
# TypeScript / JavaScript cognitive complexity (tree-sitter)
# ---------------------------------------------------------------------------

# Node types that increment complexity AND increase nesting.
_TS_NESTING_TYPES: frozenset[str] = frozenset({
    "if_statement",
    "for_statement",
    "for_in_statement",
    "while_statement",
    "do_statement",
    "switch_case",      # each case label = +1 nesting
    "catch_clause",
    "ternary_expression",
})

# Node types that increment complexity but do NOT increase nesting.
_TS_FLAT_TYPES: frozenset[str] = frozenset({
    "break_statement",
    "continue_statement",
})

_TS_JS_EXTENSIONS: frozenset[str] = frozenset({".ts", ".tsx", ".js", ".jsx"})
_SCHEMA_FILE_SUFFIXES: tuple[str, ...] = (
    ".schema.ts",
    ".schema.tsx",
    ".schema.js",
    ".schema.jsx",
)
_CONFIG_DEFAULT_FILENAME_MARKERS: tuple[str, ...] = (
    "config-defaults",
    "config.defaults",
    "default-config",
)
_SCHEMA_FILENAME_MARKERS: tuple[str, ...] = (
    "config-schema",
)


def _is_inherent_ts_complexity_context(path: Path | str) -> bool:
    """Return True for TS/JS files where high branching is often structural."""
    value = path.as_posix() if isinstance(path, Path) else path.replace("\\", "/")
    value = value.lower()

    if not any(value.endswith(ext) for ext in _TS_JS_EXTENSIONS):
        return False

    filename = value.rsplit("/", 1)[-1]
    if filename.endswith(_SCHEMA_FILE_SUFFIXES):
        return True
    if any(marker in filename for marker in _SCHEMA_FILENAME_MARKERS):
        return True
    if "migration" in filename:
        return True
    if any(marker in filename for marker in _CONFIG_DEFAULT_FILENAME_MARKERS):
        return True

    return "/migrations/" in value or "/migration/" in value


def _ts_walk(node: Any) -> list[Any]:
    """Return all descendants of a tree-sitter node."""
    stack = list(node.children)
    result: list[Any] = []
    while stack:
        child = stack.pop()
        result.append(child)
        stack.extend(child.children)
    return result


def _ts_cognitive_complexity(node: Any) -> int:
    """Compute cognitive complexity for a tree-sitter function body node."""
    return _ts_cc_recurse(node, 0)


def _ts_cc_recurse(node: Any, nesting: int) -> int:
    total = 0
    for child in node.children:
        if child.type in _TS_NESTING_TYPES:
            total += 1 + nesting
            total += _ts_cc_recurse(child, nesting + 1)
        elif child.type in (
            "function_declaration", "arrow_function",
            "method_definition", "generator_function_declaration",
        ):
            # Nested function — increase nesting without inherent increment.
            total += _ts_cc_recurse(child, nesting + 1)
        elif child.type == "binary_expression":
            # Logical operators (&&, ||, ??) contribute +1 per chain.
            op = None
            for c in child.children:
                if c.type in ("&&", "||", "??"):
                    op = c.type
            if op:
                total += 1
            total += _ts_cc_recurse(child, nesting)
        else:
            total += _ts_cc_recurse(child, nesting)
    return total


def _ts_find_functions(root: Any) -> list[Any]:
    """Find all top-level and class-level function nodes in tree-sitter AST."""
    fn_types = {
        "function_declaration",
        "method_definition",
        "arrow_function",
        "generator_function_declaration",
    }
    result: list[Any] = []
    for node in _ts_walk(root):
        if node.type in fn_types:
            result.append(node)
    return result


def _ts_function_name(node: Any) -> str:
    """Extract function name from a tree-sitter node."""
    # function_declaration, generator_function_declaration → name field
    for child in node.children:
        if child.type == "identifier":
            return str(child.text.decode("utf-8", errors="replace"))
        if child.type == "property_identifier":
            return str(child.text.decode("utf-8", errors="replace"))
    # method_definition → first property_identifier child
    # arrow_function — check parent for variable_declarator
    parent = node.parent
    if parent and parent.type == "variable_declarator":
        for child in parent.children:
            if child.type == "identifier":
                return str(child.text.decode("utf-8", errors="replace"))
    return "<anonymous>"


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------


@register_signal
class CognitiveComplexitySignal(BaseSignal):
    """Detect functions with excessive cognitive complexity."""

    incremental_scope = "file_local"

    @property
    def signal_type(self) -> SignalType:
        return SignalType.COGNITIVE_COMPLEXITY

    @property
    def name(self) -> str:
        return "Cognitive Complexity"

    _TS_LANGS = frozenset({"typescript", "tsx", "javascript", "jsx"})

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
            if is_test_file(pr.file_path):
                continue

            if pr.language == "python":
                findings.extend(
                    self._analyze_python(pr, threshold)
                )
            elif pr.language in self._TS_LANGS:
                findings.extend(
                    self._analyze_typescript(pr, threshold)
                )

        return findings

    # ------------------------------------------------------------------
    # Python path (ast-based)
    # ------------------------------------------------------------------

    def _analyze_python(
        self,
        pr: ParseResult,
        threshold: int,
    ) -> list[Finding]:
        findings: list[Finding] = []
        source = self._read_source(pr.file_path)
        if source is None:
            return findings

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return findings

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue
            body_lines = (node.end_lineno or node.lineno) - node.lineno + 1
            if body_lines < 5:
                continue

            cc = _cognitive_complexity_of_body(node.body)
            if cc <= threshold:
                continue

            findings.append(self._make_finding(
                pr, node.name, cc, threshold,
                node.lineno, node.end_lineno, body_lines,
            ))

        return findings

    # ------------------------------------------------------------------
    # TypeScript / JavaScript path (tree-sitter)
    # ------------------------------------------------------------------

    def _analyze_typescript(
        self,
        pr: ParseResult,
        threshold: int,
    ) -> list[Finding]:
        findings: list[Finding] = []
        source = self._read_source(pr.file_path)
        if source is None:
            return findings

        try:
            from drift.ingestion.ts_parser import _get_parser  # type: ignore[attr-defined]
            ts_lang = "tsx" if pr.language == "tsx" else "typescript"
            parser = _get_parser(ts_lang)
            tree = parser.parse(source.encode("utf-8"))
        except Exception:
            return findings

        dampen_for_file = _is_inherent_ts_complexity_context(pr.file_path)

        for fn_node in _ts_find_functions(tree.root_node):
            name = _ts_function_name(fn_node)
            if name.startswith("_"):
                continue
            start_line = fn_node.start_point[0] + 1
            end_line = fn_node.end_point[0] + 1
            body_lines = end_line - start_line + 1
            if body_lines < 5:
                continue

            # Find the body node (statement_block)
            body_node = None
            for child in fn_node.children:
                if child.type == "statement_block":
                    body_node = child
                    break
            if body_node is None:
                continue

            cc = _ts_cognitive_complexity(body_node)
            if cc <= threshold:
                continue

            findings.append(self._make_finding(
                pr, name, cc, threshold,
                start_line, end_line, body_lines,
                context_dampened=dampen_for_file,
            ))

        return findings

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _make_finding(
        self,
        pr: ParseResult,
        func_name: str,
        cc: int,
        threshold: int,
        start_line: int,
        end_line: int | None,
        body_lines: int,
        *,
        context_dampened: bool = False,
    ) -> Finding:
        overshoot = cc - threshold
        score = round(min(1.0, 0.3 + overshoot * 0.04), 3)
        severity = Severity.HIGH if score >= 0.7 else Severity.MEDIUM
        if context_dampened:
            score = min(score, 0.19)
            severity = Severity.INFO

        description_suffix = ""
        if context_dampened:
            description_suffix = (
                " Detected in schema/migration code where higher branching is often "
                "structural and expected; severity was capped."
            )
        return Finding(
            signal_type=self.signal_type,
            severity=severity,
            score=score,
            title=f"High cognitive complexity in {func_name}()",
            description=(
                f"Function '{func_name}' in {pr.file_path.as_posix()} has "
                f"cognitive complexity {cc} (threshold: {threshold}). "
                f"Complex control flow makes this function hard to "
                f"understand and maintain.{description_suffix}"
            ),
            file_path=pr.file_path,
            start_line=start_line,
            end_line=end_line,
            fix=(
                f"Reduce cognitive complexity of '{func_name}' "
                f"(currently {cc}, threshold {threshold}): "
                f"extract nested logic into helper functions, "
                f"replace nested conditionals with guard clauses, "
                f"simplify boolean expressions."
            ),
            metadata={
                "cognitive_complexity": cc,
                "threshold": threshold,
                "function_name": func_name,
                "body_lines": body_lines,
                "context_dampened": context_dampened,
            },
            rule_id="cognitive_complexity",
        )

    def _read_source(self, file_path: Path) -> str | None:
        try:
            target = file_path
            if self._repo_path and not file_path.is_absolute():
                target = self._repo_path / file_path
            return target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

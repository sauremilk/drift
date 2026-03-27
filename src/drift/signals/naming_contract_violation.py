"""Signal 11: Naming Contract Violation (NBV).

Detects functions whose name implies a behaviour contract that the
AST does not fulfil — e.g. ``validate_*`` without a raise/return-False
path, ``is_*`` without a bool return type.

This is a proxy for *intention drift* (EPISTEMICS §2): when a
function's name promises one thing and its body delivers another,
the declared intention and the implementation have diverged.
"""

from __future__ import annotations

import ast
import textwrap
from collections.abc import Callable
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
from drift.signals.base import BaseSignal, register_signal

# ── Naming rules ──────────────────────────────────────────────────
# Each rule: (prefix_set, description, checker_function_name)

_RULES: list[tuple[frozenset[str], str, str]] = [
    (
        frozenset({"validate_", "check_"}),
        "validate_*/check_* expects at least one raise or return False/None",
        "_has_rejection_path",
    ),
    (
        frozenset({"ensure_"}),
        "ensure_* expects at least one raise statement",
        "_has_raise",
    ),
    (
        frozenset({"get_or_create_"}),
        "get_or_create_* expects a creation path after a conditional",
        "_has_create_path",
    ),
    (
        frozenset({"is_", "has_"}),
        "is_*/has_* expects bool return type",
        "_has_bool_return",
    ),
    (
        frozenset({"try_"}),
        "try_* expects a try/except block",
        "_has_try_except",
    ),
]


def _bare_name(fn_name: str) -> str:
    """Strip class prefix: 'ClassName.method' -> 'method'."""
    return fn_name.rsplit(".", 1)[-1]


def _is_test_file(file_path: Path) -> bool:
    name = file_path.name.lower()
    return name.startswith("test_") or name.endswith("_test.py")


# ── AST checkers ──────────────────────────────────────────────────


def _has_rejection_path(tree: ast.Module) -> bool:
    """Return True if the function body contains raise or return False/None."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise):
            return True
        if isinstance(node, ast.Return) and node.value is not None:
            # return False
            if isinstance(node.value, ast.Constant) and node.value.value is False:
                return True
            # return None
            if isinstance(node.value, ast.Constant) and node.value.value is None:
                return True
    return False


def _has_raise(tree: ast.Module) -> bool:
    """Return True if the function body contains at least one raise."""
    return any(isinstance(node, ast.Raise) for node in ast.walk(tree))


def _has_create_path(tree: ast.Module) -> bool:
    """Return True if there is an assignment/call after a conditional (heuristic)."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        has_conditional = False
        for stmt in node.body:
            if isinstance(stmt, ast.If | ast.Try):
                has_conditional = True
            elif has_conditional and isinstance(stmt, ast.Assign | ast.Return):
                return True
            # Also: if/else with assignment in else branch
            if isinstance(stmt, ast.If) and stmt.orelse:
                for s in stmt.orelse:
                    if isinstance(s, ast.Assign | ast.Return | ast.Expr):
                        return True
        # Check inside if bodies for creation patterns
        for child in ast.walk(node):
            if isinstance(child, ast.If) and child.orelse:
                return True  # has branching → plausible get-or-create
    return False


def _has_bool_return(tree: ast.Module, fn_info: FunctionInfo) -> bool:
    """Return True if function has bool return type or only returns bool literals."""
    # Check annotation first
    if fn_info.return_type:
        rt = fn_info.return_type.lower().strip()
        if rt in ("bool", "builtins.bool"):
            return True

    # Check actual return statements — all must be bool constants
    returns: list[ast.Return] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and child.value is not None:
                    returns.append(child)

    if not returns:
        return False  # no explicit returns → not bool

    return all(
        isinstance(r.value, ast.Constant) and isinstance(r.value.value, bool)
        for r in returns
    )


def _has_try_except(tree: ast.Module) -> bool:
    """Return True if the function body contains a try/except block."""
    return any(isinstance(node, ast.Try) for node in ast.walk(tree))


# Map checker names to functions (typed for mypy-safe dispatch)
_CHECKERS_SIMPLE: dict[str, Callable[[ast.Module], bool]] = {
    "_has_rejection_path": _has_rejection_path,
    "_has_raise": _has_raise,
    "_has_create_path": _has_create_path,
    "_has_try_except": _has_try_except,
}

_CHECKERS_WITH_FN_INFO: dict[str, Callable[[ast.Module, FunctionInfo], bool]] = {
    "_has_bool_return": _has_bool_return,
}


def _read_function_source(
    file_path: Path, fn: FunctionInfo, repo_path: Path | None = None,
) -> str | None:
    """Read source lines for a single function."""
    try:
        target = file_path
        if repo_path and not file_path.is_absolute():
            target = repo_path / file_path
        lines = target.read_text(encoding="utf-8").splitlines()
        start = fn.start_line - 1
        end = fn.end_line
        return "\n".join(lines[start:end])
    except (OSError, UnicodeDecodeError, AttributeError):
        return None


def _match_rule(
    bare: str,
) -> tuple[frozenset[str], str, str] | None:
    """Return the first matching naming rule for a function, or None."""
    for prefixes, description, checker_name in _RULES:
        if any(bare.startswith(p) for p in prefixes):
            return prefixes, description, checker_name
    return None


@register_signal
class NamingContractViolationSignal(BaseSignal):
    """Detect functions whose name implies a contract the body does not fulfil."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.NAMING_CONTRACT_VIOLATION

    @property
    def name(self) -> str:
        return "Naming Contract Violation"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        min_loc = config.thresholds.nbv_min_function_loc
        findings: list[Finding] = []

        for pr in parse_results:
            if pr.language != "python":
                continue
            if _is_test_file(pr.file_path):
                continue

            for fn in pr.functions:
                if fn.loc < min_loc:
                    continue

                bare = _bare_name(fn.name)
                # Skip private functions
                if bare.startswith("_"):
                    continue

                rule = _match_rule(bare)
                if rule is None:
                    continue

                prefixes, description, checker_name = rule
                source = _read_function_source(pr.file_path, fn, self._repo_path)
                if source is None:
                    continue

                try:
                    tree = ast.parse(textwrap.dedent(source))
                except SyntaxError:
                    continue

                # _has_bool_return needs fn_info for annotation check
                if checker_name == "_has_bool_return":
                    checker_with_fn_info = _CHECKERS_WITH_FN_INFO[checker_name]
                    satisfied = checker_with_fn_info(tree, fn)
                else:
                    checker_simple = _CHECKERS_SIMPLE[checker_name]
                    satisfied = checker_simple(tree)

                if satisfied:
                    continue

                # Violation found
                matched_prefix = next(
                    p for p in prefixes if bare.startswith(p)
                )
                score = 0.6
                findings.append(
                    Finding(
                        signal_type=self.signal_type,
                        severity=Severity.MEDIUM,
                        score=score,
                        title=f"Naming contract violation: {fn.name}()",
                        description=(
                            f"Function '{fn.name}' has prefix '{matched_prefix}' "
                            f"but does not satisfy the expected contract: "
                            f"{description}."
                        ),
                        file_path=pr.file_path,
                        start_line=fn.start_line,
                        end_line=fn.end_line,
                        fix=(
                            f"Either add the missing behaviour to '{fn.name}()' "
                            f"(e.g. a raise statement or appropriate return) "
                            f"or rename it to reflect its actual purpose."
                        ),
                        metadata={
                            "function_name": fn.name,
                            "prefix_rule": matched_prefix,
                            "expected_contract": description,
                            "checker": checker_name,
                        },
                    )
                )

        return findings

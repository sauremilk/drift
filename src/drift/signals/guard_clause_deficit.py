"""Signal 10: Guard Clause Deficit (GCD).

Detects modules where public, non-trivial functions uniformly lack
input validation guards — a structural proxy for "blind trust" data
flow where parameters are consumed without checking.

Epistemics: Cannot detect WHICH validations are needed, but CAN detect
the structural pattern of uniform absence of guard clauses that
correlates with missing input contracts.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    FunctionInfo,
    ParseResult,
    SignalType,
    severity_for_score,
)
from drift.signals.base import BaseSignal, register_signal

# Type annotations considered "narrow" enough to count as partial guards
_BROAD_TYPES: frozenset[str] = frozenset({
    "Any", "dict", "list", "object", "tuple", "set",
})


def _is_test_file(file_path: Path) -> bool:
    name = file_path.name.lower()
    return name.startswith("test_") or name.endswith("_test.py")


def _is_qualifying(func: FunctionInfo) -> bool:
    """Determine if a function qualifies for guard-clause analysis."""
    # Only public functions
    if func.name.startswith("_"):
        return False
    # Need at least 2 parameters (non-trivial signature)
    if len(func.parameters) < 2:
        return False
    # Need meaningful complexity
    return func.complexity >= 5


def _has_guard_clause(source_lines: list[str], func: FunctionInfo) -> bool:
    """Check if a function has guard clauses in its early body.

    Parses only the function body and inspects the first ~30% of
    statements for isinstance, assert, or if-raise/return patterns
    referencing parameters.
    """
    # Extract function source
    start = func.start_line - 1
    end = func.end_line
    func_source = "\n".join(source_lines[start:end])
    try:
        tree = ast.parse(func_source)
    except SyntaxError:
        return False

    # Find the function def
    func_def: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_def = node
            break

    if func_def is None or not func_def.body:
        return False

    # Collect parameter names
    params = {arg.arg for arg in func_def.args.args}
    params |= {arg.arg for arg in func_def.args.kwonlyargs}
    if func_def.args.vararg:
        params.add(func_def.args.vararg.arg)
    if func_def.args.kwarg:
        params.add(func_def.args.kwarg.arg)
    # Discard 'self'/'cls'
    params -= {"self", "cls"}

    if not params:
        return False

    # Inspect early statements (first 30% of body)
    body = func_def.body
    early_limit = max(1, len(body) * 30 // 100)
    early_stmts = body[:early_limit]

    return any(_stmt_is_guard(stmt, params) for stmt in early_stmts)


def _stmt_is_guard(stmt: ast.stmt, params: set[str]) -> bool:
    """Return True if a statement is a guard clause referencing parameters."""
    # assert <expr involving params>
    if isinstance(stmt, ast.Assert) and _references_params(stmt.test, params):
        return True

    # if <check>: raise / return
    if isinstance(stmt, ast.If) and _references_params(stmt.test, params):
        for child in stmt.body:
            if isinstance(child, (ast.Raise, ast.Return)):
                return True

    # Expression containing isinstance() call
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Call)
        and _is_isinstance_call(stmt.value, params)
    )


def _references_params(node: ast.expr, params: set[str]) -> bool:
    """Return True if any Name node in the expression references a parameter."""
    return any(
        isinstance(child, ast.Name) and child.id in params
        for child in ast.walk(node)
    )


def _is_isinstance_call(call: ast.Call, params: set[str]) -> bool:
    """Return True if this is isinstance(param, ...)."""
    func = call.func
    return (
        isinstance(func, ast.Name)
        and func.id == "isinstance"
        and bool(call.args)
        and isinstance(call.args[0], ast.Name)
        and call.args[0].id in params
    )


def _has_narrow_annotations(func: FunctionInfo) -> bool:
    """Return True if the function has non-broad type annotations (partial guard)."""
    # Check parameter annotations from AST fingerprint if available
    # Fall back to checking return type as proxy
    return bool(func.return_type and func.return_type not in _BROAD_TYPES)


@register_signal
class GuardClauseDeficitSignal(BaseSignal):
    """Detect modules with uniformly unguarded public functions."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.GUARD_CLAUSE_DEFICIT

    @property
    def name(self) -> str:
        return "Guard Clause Deficit"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        min_qualifying = config.thresholds.gcd_min_public_functions

        # Group qualifying functions by module
        module_funcs: dict[Path, list[FunctionInfo]] = defaultdict(list)
        module_sources: dict[Path, list[str]] = {}

        for pr in parse_results:
            if pr.language != "python":
                continue
            if _is_test_file(pr.file_path):
                continue
            # Skip __init__.py (thin namespace modules)
            if pr.file_path.name == "__init__.py":
                continue

            qualifying = [f for f in pr.functions if _is_qualifying(f)]
            if not qualifying:
                continue

            module = pr.file_path.parent
            module_funcs[module].extend(qualifying)

            # Lazy-load source only once per file
            if pr.file_path not in module_sources:
                try:
                    source = pr.file_path.read_text(
                        encoding="utf-8", errors="replace"
                    )
                    module_sources[pr.file_path] = source.splitlines()
                except OSError:
                    module_sources[pr.file_path] = []

        findings: list[Finding] = []

        for module, funcs in module_funcs.items():
            if len(funcs) < min_qualifying:
                continue

            guarded = 0
            unguarded_funcs: list[FunctionInfo] = []
            total_complexity = 0

            for func in funcs:
                source_lines = module_sources.get(func.file_path, [])
                if not source_lines:
                    continue

                has_guard = _has_guard_clause(source_lines, func)
                has_narrow = _has_narrow_annotations(func)

                if has_guard or has_narrow:
                    guarded += 1
                else:
                    unguarded_funcs.append(func)
                    total_complexity += func.complexity

            total = len(funcs)
            if total == 0:
                continue

            guarded_ratio = guarded / total
            if guarded_ratio >= 0.15:
                continue

            # Score: severity scales with complexity of unguarded functions
            mean_complexity = total_complexity / max(1, len(unguarded_funcs))
            score = min(1.0, (1.0 - guarded_ratio) * mean_complexity / 20)
            severity = severity_for_score(score)

            # Collect affected files
            affected = sorted({f.file_path for f in unguarded_funcs})

            findings.append(
                Finding(
                    signal_type=SignalType.GUARD_CLAUSE_DEFICIT,
                    severity=severity,
                    score=score,
                    title=f"Guard-Clause-Defizit: {module}",
                    description=(
                        f"{len(unguarded_funcs)}/{total} öffentliche Funktionen "
                        f"ohne Eingabe-Guards (Guarded-Ratio: {guarded_ratio:.1%}). "
                        f"Mittlere Complexity der ungeschützten Funktionen: "
                        f"{mean_complexity:.1f}."
                    ),
                    file_path=affected[0] if affected else None,
                    related_files=affected[1:],
                    fix=(
                        f"Modul {module.name}: Füge isinstance-Checks, "
                        f"assert-Statements oder if-raise Guards in die "
                        f"ersten Zeilen der öffentlichen Funktionen ein."
                    ),
                    metadata={
                        "total_qualifying": total,
                        "guarded_count": guarded,
                        "unguarded_count": len(unguarded_funcs),
                        "guarded_ratio": guarded_ratio,
                        "mean_complexity_unguarded": mean_complexity,
                        "unguarded_functions": [
                            f.name for f in unguarded_funcs[:10]
                        ],
                    },
                )
            )

        return findings

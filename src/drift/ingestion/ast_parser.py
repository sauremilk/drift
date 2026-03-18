"""Python AST parser using the built-in ast module.

Uses Python's standard library ast module for zero-dependency Python parsing.
TypeScript support requires the optional tree-sitter dependency.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

from drift.models import (
    ClassInfo,
    FunctionInfo,
    ImportInfo,
    ParseResult,
    PatternCategory,
    PatternInstance,
)

# ---------------------------------------------------------------------------
# Cyclomatic complexity
# ---------------------------------------------------------------------------


class _ComplexityCounter(ast.NodeVisitor):
    """Count decision points for cyclomatic complexity."""

    def __init__(self) -> None:
        self.complexity = 1

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.complexity += 1
        self.generic_visit(node)


def _cyclomatic_complexity(node: ast.AST) -> int:
    counter = _ComplexityCounter()
    counter.visit(node)
    return counter.complexity


# ---------------------------------------------------------------------------
# Error handling pattern fingerprinting
# ---------------------------------------------------------------------------


def _fingerprint_try_block(node: ast.Try) -> dict[str, Any]:
    """Extract a structural fingerprint from a try/except block."""
    handlers: list[dict[str, Any]] = []
    for handler in node.handlers:
        exc_type = "bare"
        if handler.type is not None:
            if isinstance(handler.type, ast.Name):
                exc_type = handler.type.id
            elif isinstance(handler.type, ast.Attribute):
                exc_type = ast.dump(handler.type)
            elif isinstance(handler.type, ast.Tuple):
                exc_type = "|".join(
                    getattr(e, "id", ast.dump(e)) for e in handler.type.elts
                )

        body_actions: list[str] = []
        for stmt in handler.body:
            if isinstance(stmt, ast.Raise):
                body_actions.append("raise")
            elif isinstance(stmt, ast.Return):
                body_actions.append("return")
            elif isinstance(stmt, ast.Pass):
                body_actions.append("pass")
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                func = stmt.value.func
                if isinstance(func, ast.Attribute):
                    if func.attr in ("error", "exception", "warning", "critical"):
                        body_actions.append("log")
                    elif func.attr == "print":
                        body_actions.append("print")
                    else:
                        body_actions.append("call")
                elif isinstance(func, ast.Name):
                    if func.id == "print":
                        body_actions.append("print")
                    elif func.id in ("logging", "logger", "log"):
                        body_actions.append("log")
                    else:
                        body_actions.append("call")
                else:
                    body_actions.append("call")
            else:
                body_actions.append("other")

        handlers.append(
            {
                "exception_type": exc_type,
                "actions": body_actions,
            }
        )

    return {
        "handler_count": len(node.handlers),
        "handlers": handlers,
        "has_finally": bool(node.finalbody),
        "has_else": bool(node.orelse),
    }


# ---------------------------------------------------------------------------
# API endpoint pattern fingerprinting
# ---------------------------------------------------------------------------

_ROUTE_DECORATORS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "head",
    "options",
    "route",
    "api_view",
    "action",
}


def _is_route_decorator(decorator: ast.expr) -> bool:
    if isinstance(decorator, ast.Call):
        decorator = decorator.func
    if isinstance(decorator, ast.Attribute):
        return decorator.attr.lower() in _ROUTE_DECORATORS
    if isinstance(decorator, ast.Name):
        return decorator.id.lower() in _ROUTE_DECORATORS
    return False


def _fingerprint_endpoint(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, Any] | None:
    """Extract pattern fingerprint for an API endpoint function."""
    route_decorators = [d for d in node.decorator_list if _is_route_decorator(d)]
    if not route_decorators:
        return None

    has_try = False
    has_auth_check = False
    return_patterns: list[str] = []

    for child in ast.walk(node):
        if isinstance(child, ast.Try):
            has_try = True
        if isinstance(child, ast.Name) and child.id in (
            "current_user",
            "get_current_user",
            "Depends",
        ):
            has_auth_check = True
        if isinstance(child, ast.Return) and child.value:
            if isinstance(child.value, ast.Call):
                func = child.value.func
                if isinstance(func, ast.Name):
                    return_patterns.append(func.id)
                elif isinstance(func, ast.Attribute):
                    return_patterns.append(func.attr)

    return {
        "has_error_handling": has_try,
        "has_auth": has_auth_check,
        "return_patterns": return_patterns,
        "is_async": isinstance(node, ast.AsyncFunctionDef),
    }


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------


class PythonFileParser(ast.NodeVisitor):
    """Parse a Python file and extract structural information."""

    def __init__(self, source: str, file_path: Path) -> None:
        self.source = source
        self.file_path = file_path
        self._lines = source.splitlines()
        self.functions: list[FunctionInfo] = []
        self.classes: list[ClassInfo] = []
        self.imports: list[ImportInfo] = []
        self.patterns: list[PatternInstance] = []
        self._current_class: str | None = None

    def parse(self) -> ParseResult:
        try:
            tree = ast.parse(self.source, filename=str(self.file_path))
        except SyntaxError as exc:
            return ParseResult(
                file_path=self.file_path,
                language="python",
                line_count=len(self._lines),
                parse_errors=[str(exc)],
            )

        self.visit(tree)

        return ParseResult(
            file_path=self.file_path,
            language="python",
            functions=self.functions,
            classes=self.classes,
            imports=self.imports,
            patterns=self.patterns,
            line_count=len(self._lines),
        )

    # -- Functions ----------------------------------------------------------

    def _process_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(f"{ast.dump(dec)}")
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    decorators.append(dec.func.attr)

        params = []
        for arg in node.args.args:
            if arg.arg != "self" and arg.arg != "cls":
                params.append(arg.arg)

        return_type = None
        if node.returns:
            try:
                return_type = ast.unparse(node.returns)
            except Exception:
                return_type = "unknown"

        has_docstring = (
            bool(node.body)
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        )

        body_source = ast.get_source_segment(self.source, node) or ""
        body_hash = hashlib.sha256(body_source.encode()).hexdigest()[:16]

        func_name = node.name
        if self._current_class:
            func_name = f"{self._current_class}.{node.name}"

        info = FunctionInfo(
            name=func_name,
            file_path=self.file_path,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            language="python",
            complexity=_cyclomatic_complexity(node),
            loc=(node.end_lineno or node.lineno) - node.lineno + 1,
            parameters=params,
            return_type=return_type,
            decorators=decorators,
            has_docstring=has_docstring,
            body_hash=body_hash,
        )
        self.functions.append(info)

        # Extract error handling patterns inside this function
        for child in ast.walk(node):
            if isinstance(child, ast.Try):
                fp = _fingerprint_try_block(child)
                self.patterns.append(
                    PatternInstance(
                        category=PatternCategory.ERROR_HANDLING,
                        file_path=self.file_path,
                        function_name=func_name,
                        start_line=child.lineno,
                        end_line=child.end_lineno or child.lineno,
                        fingerprint=fp,
                    )
                )

        # Extract API endpoint patterns
        ep_fp = _fingerprint_endpoint(node)
        if ep_fp is not None:
            self.patterns.append(
                PatternInstance(
                    category=PatternCategory.API_ENDPOINT,
                    file_path=self.file_path,
                    function_name=func_name,
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    fingerprint=ep_fp,
                )
            )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._process_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._process_function(node)
        self.generic_visit(node)

    # -- Classes ------------------------------------------------------------

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                try:
                    bases.append(ast.unparse(base))
                except Exception:
                    bases.append("unknown")

        has_docstring = (
            bool(node.body)
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        )

        prev_class = self._current_class
        self._current_class = node.name

        class_info = ClassInfo(
            name=node.name,
            file_path=self.file_path,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            language="python",
            bases=bases,
            has_docstring=has_docstring,
        )

        self.generic_visit(node)

        # Collect methods that were added while visiting this class
        class_info.methods = [
            f for f in self.functions if f.name.startswith(f"{node.name}.")
        ]

        self.classes.append(class_info)
        self._current_class = prev_class

    # -- Imports ------------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(
                ImportInfo(
                    source_file=self.file_path,
                    imported_module=alias.name,
                    imported_names=[alias.asname or alias.name],
                    line_number=node.lineno,
                    is_relative=False,
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        names = [alias.name for alias in (node.names or [])]
        self.imports.append(
            ImportInfo(
                source_file=self.file_path,
                imported_module=module,
                imported_names=names,
                line_number=node.lineno,
                is_relative=(node.level or 0) > 0,
            )
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_python_file(file_path: Path, repo_path: Path) -> ParseResult:
    """Parse a Python file and return structural information."""
    full_path = repo_path / file_path
    source = full_path.read_text(encoding="utf-8", errors="replace")
    parser = PythonFileParser(source, file_path)
    return parser.parse()


def parse_file(file_path: Path, repo_path: Path, language: str) -> ParseResult:
    """Parse a source file based on its language."""
    if language == "python":
        return parse_python_file(file_path, repo_path)

    if language in ("typescript", "tsx"):
        return _parse_typescript_stub(file_path, repo_path)

    return ParseResult(
        file_path=file_path,
        language=language,
        parse_errors=[f"Unsupported language: {language}"],
    )


def _parse_typescript_stub(file_path: Path, repo_path: Path) -> ParseResult:
    """Minimal TypeScript parsing — imports and line count only.

    Full TypeScript AST parsing requires tree-sitter (optional dependency).
    """
    full_path = repo_path / file_path
    source = full_path.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()

    imports: list[ImportInfo] = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            # Simple regex-free detection of TS imports
            if " from " in stripped:
                parts = stripped.split(" from ")
                module = parts[-1].strip().strip("'\";")
                names_part = parts[0].replace("import", "").strip()
                names = [
                    n.strip().strip("{}") for n in names_part.split(",") if n.strip()
                ]
                imports.append(
                    ImportInfo(
                        source_file=file_path,
                        imported_module=module,
                        imported_names=names,
                        line_number=i,
                        is_relative=module.startswith("."),
                    )
                )

    return ParseResult(
        file_path=file_path,
        language="typescript",
        imports=imports,
        line_count=len(lines),
    )

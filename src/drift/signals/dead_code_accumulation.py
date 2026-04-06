"""Signal: Dead Code Accumulation (DCA).

Detects exported functions and classes that are never imported anywhere
else in the codebase, indicating potentially dead code.

Dead code increases maintenance cost, confuses contributors, and can
mask real issues by inflating code metrics.

Known limitations (documented, not suppressed):
- Dynamic imports (importlib, __import__) may cause false positives.
- Framework entry-points (CLI commands, signal handlers, etc.) may be
  flagged if they are only referenced in configuration files.

Deterministic, AST-only, LLM-free.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    ParseResult,
    Severity,
    SignalType,
)
from drift.signals._utils import (
    _SUPPORTED_LANGUAGES,
    is_library_finding_path,
    is_likely_library_repo,
    is_test_file,
)
from drift.signals.base import BaseSignal, register_signal

# Files that typically re-export or serve as entry points.
_SKIP_FILES: frozenset[str] = frozenset({
    "__init__.py",
    "__main__.py",
    "conftest.py",
    "setup.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "index.ts",
    "index.tsx",
    "index.js",
    "index.jsx",
})

# Common names that are framework-invoked rather than explicitly imported.
_FRAMEWORK_NAMES: frozenset[str] = frozenset({
    "main",
    "cli",
    "app",
    "create_app",
    "setup",
    "teardown",
    "configure",
    "register",
    "migrate",
    "upgrade",
    "downgrade",
})

_ROUTE_DECORATOR_TOKENS: frozenset[str] = frozenset({
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "options",
    "head",
    "route",
    "websocket",
    "api_view",
})

_SCHEMA_CLASS_SUFFIXES: tuple[str, ...] = (
    "Schema",
    "Model",
    "DTO",
    "Request",
    "Response",
)

_APPLICATION_LAYOUT_TOKENS: frozenset[str] = frozenset({
    "app",
    "apps",
    "backend",
    "frontend",
    "service",
    "services",
    "server",
    "web",
})

_INTERNAL_LIBRARY_PATH_TOKENS: frozenset[str] = frozenset({
    "internal",
    "_internal",
    "private",
    "_private",
    "impl",
    "generated",
})

_SCRIPT_PATH_TOKENS: frozenset[str] = frozenset({
    "scripts",
    "tools",
    "bin",
    "workflows",
})


def _is_script_context_path(file_path: Path) -> bool:
    """Return True for path contexts that are likely executable scripts."""
    tokens = _path_tokens(file_path)
    if not tokens:
        return False

    if len(tokens) >= 2 and tokens[0] == ".github" and tokens[1] == "workflows":
        return True

    return any(token in _SCRIPT_PATH_TOKENS for token in tokens)


def _path_tokens(file_path: Path) -> list[str]:
    """Return lowercase path tokens for deterministic path heuristics."""
    return [token for token in file_path.as_posix().lower().split("/") if token]


def _has_application_layout(parse_results: list[ParseResult]) -> bool:
    """Return True when parse results indicate a classic application layout."""
    tokens: set[str] = set()
    for pr in parse_results:
        if pr.language not in _SUPPORTED_LANGUAGES:
            continue
        if is_test_file(pr.file_path):
            continue
        tokens.update(_path_tokens(pr.file_path))
    return any(token in _APPLICATION_LAYOUT_TOKENS for token in tokens)


def _discover_package_roots(parse_results: list[ParseResult]) -> set[str]:
    """Discover top-level package roots from __init__.py files.

    This targets library/framework repositories that expose symbols via
    package modules (e.g. fastapi/applications.py) without requiring
    internal imports for external API usage.
    """
    package_roots: set[str] = set()
    for pr in parse_results:
        if pr.language not in _SUPPORTED_LANGUAGES:
            continue
        if is_test_file(pr.file_path):
            continue
        if pr.file_path.name != "__init__.py":
            continue

        tokens = _path_tokens(pr.file_path)
        if len(tokens) < 2:
            continue

        root = tokens[0]
        if root in {"src", "lib", "packages", "tests", "test", "docs"}:
            continue
        package_roots.add(root)

    return package_roots


def _is_public_api_package_path(file_path: Path, package_roots: set[str]) -> bool:
    """Return True for package-layout modules that likely expose public API."""
    if not package_roots:
        return False

    tokens = _path_tokens(file_path)
    if not tokens:
        return False
    if tokens[0] not in package_roots:
        return False
    return not any(token in _INTERNAL_LIBRARY_PATH_TOKENS for token in tokens)


def _is_route_entrypoint_function(decorators: list[str]) -> bool:
    """Return True when decorators indicate a framework route entry-point."""
    for dec in decorators:
        token = dec.split(".")[-1].lower()
        if token in _ROUTE_DECORATOR_TOKENS:
            return True
    return False


def _is_schema_like_class(name: str, bases: list[str]) -> bool:
    """Return True for classes that likely represent API/Pydantic schemas."""
    if name.endswith(_SCHEMA_CLASS_SUFFIXES):
        return True

    for base in bases:
        base_token = base.split(".")[-1]
        if base_token in {"BaseModel", "SQLModel", "Schema"}:
            return True
    return False


def _is_public(name: str) -> bool:
    """Return True if *name* is a public symbol (no leading underscore)."""
    return not name.startswith("_")


@register_signal
class DeadCodeAccumulationSignal(BaseSignal):
    """Detect exported symbols that are never imported elsewhere."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.DEAD_CODE_ACCUMULATION

    @property
    def name(self) -> str:
        return "Dead Code Accumulation"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        ignore_re_exports = config.thresholds.dca_ignore_re_exports
        has_application_layout = _has_application_layout(parse_results)
        package_roots = (
            set() if has_application_layout else _discover_package_roots(parse_results)
        )
        library_repo = is_likely_library_repo(parse_results) or bool(package_roots)

        # Phase 1: collect all exported (public) symbols per file
        # symbol_name → list of (file_path, kind, start_line)
        exported: dict[str, list[tuple[Path, str, int]]] = defaultdict(list)
        route_entrypoint_files: set[Path] = set()

        for pr in parse_results:
            if pr.language not in _SUPPORTED_LANGUAGES:
                continue
            for fn in pr.functions:
                if _is_route_entrypoint_function(fn.decorators):
                    route_entrypoint_files.add(pr.file_path)
                    break

        for pr in parse_results:
            if pr.language not in _SUPPORTED_LANGUAGES:
                continue
            if is_test_file(pr.file_path):
                continue
            if pr.language == "python" and _is_script_context_path(pr.file_path):
                # Script-like modules are typically executed, not imported.
                continue

            file_name = pr.file_path.name
            if file_name in _SKIP_FILES and ignore_re_exports:
                    continue

            for fn in pr.functions:
                if _is_route_entrypoint_function(fn.decorators):
                    continue
                if _is_public(fn.name) and fn.name not in _FRAMEWORK_NAMES:
                    exported[fn.name].append(
                        (pr.file_path, "function", fn.start_line)
                    )

            for cls in pr.classes:
                if (
                    pr.file_path in route_entrypoint_files
                    and _is_schema_like_class(cls.name, cls.bases)
                ):
                    continue
                if _is_public(cls.name) and cls.name not in _FRAMEWORK_NAMES:
                    exported[cls.name].append(
                        (pr.file_path, "class", cls.start_line)
                    )

        # Phase 2: collect all imported names across the entire codebase
        imported_names: set[str] = set()
        for pr in parse_results:
            for imp in pr.imports:
                for name in imp.imported_names:
                    imported_names.add(name)
                # Also count the module itself (from X import Y → Y is used)
                # and dotted access patterns
                parts = imp.imported_module.split(".")
                for part in parts:
                    imported_names.add(part)

        # Phase 3: find symbols that are exported but never imported
        findings: list[Finding] = []
        # Group dead symbols by file for aggregate findings
        dead_by_file: dict[Path, list[tuple[str, str, int]]] = defaultdict(list)
        suppressed_public_api_by_file: dict[Path, list[tuple[str, str, int]]] = (
            defaultdict(list)
        )

        for symbol_name, locations in exported.items():
            if symbol_name in imported_names:
                continue
            for file_path, kind, start_line in locations:
                if library_repo and _is_public_api_package_path(file_path, package_roots):
                    suppressed_public_api_by_file[file_path].append(
                        (symbol_name, kind, start_line)
                    )
                    continue
                dead_by_file[file_path].append((symbol_name, kind, start_line))

        for file_path, dead_symbols in dead_by_file.items():
            if not dead_symbols:
                continue

            # Count total exports for this file
            total_exports = sum(
                1
                for sym, locs in exported.items()
                for fp, _, _ in locs
                if fp == file_path
            )

            dead_count = len(dead_symbols)
            dead_ratio = dead_count / max(1, total_exports)

            # Only flag files with meaningful dead code accumulation
            if dead_count < 2:
                continue

            score = round(min(1.0, dead_ratio * 0.8 + dead_count * 0.02), 3)
            severity = Severity.HIGH if score >= 0.7 else Severity.MEDIUM
            dead_names = [s[0] for s in dead_symbols[:10]]

            # Use line of first dead symbol for SARIF region support (#88)
            first_dead_line = dead_symbols[0][2] if dead_symbols[0][2] else None

            findings.append(
                Finding(
                    signal_type=self.signal_type,
                    severity=severity,
                    score=score,
                    title=(
                        f"{dead_count} potentially unused exports "
                        f"in {file_path.name}"
                    ),
                    description=(
                        f"{file_path} exports {dead_count}/{total_exports} "
                        f"public symbols that are never imported elsewhere: "
                        f"{', '.join(dead_names)}"
                        f"{'…' if dead_count > 10 else ''}. "
                        f"Dead code increases maintenance cost and confuses "
                        f"contributors."
                    ),
                    file_path=file_path,
                    start_line=first_dead_line,
                    fix=(
                        f"Review and remove {dead_count} unused exports in "
                        f"{file_path.name}: {', '.join(dead_names)}. "
                        f"If they are framework entry-points or dynamically "
                        f"loaded, mark with # drift:ignore or add to "
                        f"exclude patterns."
                    ),
                    metadata={
                        "dead_symbols": [
                            {"name": s[0], "kind": s[1], "line": s[2]}
                            for s in dead_symbols
                        ],
                        "dead_count": dead_count,
                        "total_exports": total_exports,
                        "dead_ratio": round(dead_ratio, 3),
                        "library_context_candidate": library_repo
                        and (
                            is_library_finding_path(file_path)
                            or _is_public_api_package_path(file_path, package_roots)
                        ),
                    },
                    rule_id="dead_code_accumulation",
                )
            )

        return findings

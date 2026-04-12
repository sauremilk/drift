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

import json
from collections import defaultdict
from pathlib import Path

from drift.config import DriftConfig
from drift.ingestion.test_detection import classify_file_context
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

_RUNTIME_PLUGIN_CONFIG_ROOT_TOKENS: frozenset[str] = frozenset({
    "extensions",
    "plugins",
})

_RUNTIME_PLUGIN_CONFIG_BASENAMES: frozenset[str] = frozenset({
    "config.ts",
    "config.tsx",
    "config.js",
    "config.jsx",
    "config.mjs",
    "config.cjs",
})

_RUNTIME_PLUGIN_ENTRYPOINT_PATH_TOKENS: frozenset[str] = frozenset({
    "components",
    "component",
    "plugin-sdk",
    "plugin_sdk",
    "sdk",
})

_RUNTIME_PLUGIN_ENTRYPOINT_BASENAMES: frozenset[str] = frozenset({
    "components.ts",
    "components.tsx",
    "components.js",
    "components.jsx",
})

_RUNTIME_PLUGIN_WORKSPACE_SOURCE_SUFFIXES: frozenset[str] = frozenset({
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mts",
    ".cts",
    ".mjs",
    ".cjs",
})

_PUBLISHED_PACKAGE_SOURCE_ROOTS: frozenset[str] = frozenset({"src", "lib"})


def _relative_to_or_none(path: Path, base: Path) -> Path | None:
    """Return *path* relative to *base* or None when not contained."""
    try:
        return path.relative_to(base)
    except ValueError:
        return None


def _extract_package_root_candidates(file_path: Path) -> list[Path]:
    """Extract packages/<name> root candidates from a file path."""
    parts = file_path.parts
    if len(parts) < 3:
        return []

    candidates: list[Path] = []
    lowered_parts = [part.lower() for part in parts]
    for idx, token in enumerate(lowered_parts[:-1]):
        if token != "packages" or idx + 1 >= len(parts):
            continue
        candidates.append(Path(*parts[: idx + 2]))

    return candidates


def _discover_published_package_roots(parse_results: list[ParseResult]) -> dict[Path, str]:
    """Return package roots with non-private npm package.json name metadata."""
    package_roots: dict[Path, str] = {}

    for pr in parse_results:
        if pr.language not in _SUPPORTED_LANGUAGES:
            continue

        for package_root in _extract_package_root_candidates(pr.file_path):
            package_json = package_root / "package.json"
            if not package_json.is_file():
                continue

            try:
                package_data = json.loads(package_json.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            package_name = package_data.get("name")
            is_private = package_data.get("private") is True
            if not isinstance(package_name, str) or not package_name.strip() or is_private:
                continue

            package_roots[package_root] = package_name

    return package_roots


def _published_package_name_for_source(
    file_path: Path,
    published_package_roots: dict[Path, str],
) -> str | None:
    """Return npm package name when *file_path* belongs to a published package."""
    suffix = file_path.suffix.lower()
    if suffix not in _RUNTIME_PLUGIN_WORKSPACE_SOURCE_SUFFIXES:
        return None

    for package_root, package_name in published_package_roots.items():
        rel_path = _relative_to_or_none(file_path, package_root)
        if rel_path is None or not rel_path.parts:
            continue
        if rel_path.parts[0].lower() in _PUBLISHED_PACKAGE_SOURCE_ROOTS:
            return package_name

    return None


def _is_testkit_contract_path(file_path: Path) -> bool:
    """Return True for testkit contract modules consumed by downstream tests.

    Files like `*.testkit.ts` or `*.testkit.js` commonly expose reusable
    test contracts/harness APIs that are intentionally consumed outside the
    local static import graph.
    """
    suffix = file_path.suffix.lower()
    if suffix not in _RUNTIME_PLUGIN_WORKSPACE_SOURCE_SUFFIXES:
        return False

    file_name = file_path.name.lower()
    return ".testkit." in file_name


def _is_runtime_plugin_workspace_path(file_path: Path) -> bool:
    """Return True for files inside extension/plugin workspaces.

    In monorepos, these exports are often consumed by host runtime loaders
    across package boundaries and can appear dead in static import-only views.
    """
    tokens = _path_tokens(file_path)
    if len(tokens) < 3:
        return False

    for idx, token in enumerate(tokens[:-1]):
        if token not in _RUNTIME_PLUGIN_CONFIG_ROOT_TOKENS:
            continue
        # Require at least one path segment after extensions/plugins.
        if idx + 1 < len(tokens):
            return True
    return False


def _is_runtime_plugin_workspace_source_file(file_path: Path) -> bool:
    """Return True for JS/TS source files inside runtime plugin workspaces."""
    if file_path.suffix.lower() not in _RUNTIME_PLUGIN_WORKSPACE_SOURCE_SUFFIXES:
        return False
    return _is_runtime_plugin_workspace_path(file_path)


def _is_script_context_path(file_path: Path) -> bool:
    """Return True for path contexts that are likely executable scripts."""
    tokens = _path_tokens(file_path)
    if not tokens:
        return False

    if len(tokens) >= 2 and tokens[0] == ".github" and tokens[1] == "workflows":
        return True

    return any(token in _SCRIPT_PATH_TOKENS for token in tokens)


def _is_runtime_plugin_config_path(file_path: Path) -> bool:
    """Return True for plugin/extension config modules often loaded dynamically."""
    tokens = _path_tokens(file_path)
    if len(tokens) < 3:
        return False

    if tokens[0] not in _RUNTIME_PLUGIN_CONFIG_ROOT_TOKENS:
        return False

    file_name = file_path.name.lower()
    if file_name in _RUNTIME_PLUGIN_CONFIG_BASENAMES:
        return True

    return file_name.startswith("config-")


def _is_runtime_plugin_entrypoint_path(file_path: Path) -> bool:
    """Return True for plugin/extension entrypoint modules loaded indirectly."""
    tokens = _path_tokens(file_path)
    if len(tokens) < 3:
        return False

    if tokens[0] not in _RUNTIME_PLUGIN_CONFIG_ROOT_TOKENS:
        return False

    file_name = file_path.name.lower()
    if file_name in _RUNTIME_PLUGIN_ENTRYPOINT_BASENAMES:
        return True

    return any(
        token in _RUNTIME_PLUGIN_ENTRYPOINT_PATH_TOKENS for token in tokens
    )


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
        handling = config.test_file_handling or "reduce_severity"
        has_application_layout = _has_application_layout(parse_results)
        package_roots = (
            set() if has_application_layout else _discover_package_roots(parse_results)
        )
        library_repo = is_likely_library_repo(parse_results) or bool(package_roots)
        published_package_roots = _discover_published_package_roots(parse_results)

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
            if is_test_file(pr.file_path) and handling == "exclude":
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
                if (
                    pr.language in {"typescript", "javascript"}
                    and not fn.is_exported
                ):
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
                if (
                    pr.language in {"typescript", "javascript"}
                    and not cls.is_exported
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
            path_context = classify_file_context(file_path)
            testkit_contract_heuristic_applied = False
            if _is_testkit_contract_path(file_path):
                score = round(score * 0.45, 3)
                severity = Severity.LOW
                testkit_contract_heuristic_applied = True
            elif path_context == "test" and handling == "reduce_severity":
                score = round(score * 0.45, 3)
                severity = Severity.LOW

            runtime_plugin_config_heuristic_applied = False
            runtime_plugin_entrypoint_heuristic_applied = False
            runtime_plugin_workspace_heuristic_applied = False
            published_package_heuristic_applied = False
            published_package_name: str | None = None
            if (
                path_context != "test"
                and _is_runtime_plugin_config_path(file_path)
            ):
                # Plugin config modules are frequently loaded via runtime import()
                # patterns and cannot be resolved reliably with static imports only.
                score = round(min(0.69, score * 0.6), 3)
                severity = Severity.MEDIUM
                runtime_plugin_config_heuristic_applied = True
            elif (
                path_context != "test"
                and _is_runtime_plugin_entrypoint_path(file_path)
            ):
                # Plugin entrypoint modules (components/plugin-sdk) are often
                # consumed via host registries and dynamic framework wiring.
                score = round(min(0.69, score * 0.6), 3)
                severity = Severity.MEDIUM
                runtime_plugin_entrypoint_heuristic_applied = True
            elif (
                path_context != "test"
                and _is_runtime_plugin_workspace_source_file(file_path)
            ):
                # Workspace exports are commonly consumed via host runtime/plugin
                # loader boundaries that static import graphs do not resolve.
                score = round(min(0.39, score * 0.45), 3)
                severity = Severity.LOW
                runtime_plugin_workspace_heuristic_applied = True
            elif path_context != "test":
                published_package_name = _published_package_name_for_source(
                    file_path,
                    published_package_roots,
                )
                if published_package_name:
                    # Published npm package exports are often consumed by
                    # downstream users and can appear dead in monorepo-only
                    # static import graphs.
                    score = round(min(0.39, score * 0.45), 3)
                    severity = Severity.LOW
                    published_package_heuristic_applied = True

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
                        "library_context_candidate": (
                            library_repo
                            and (
                                is_library_finding_path(file_path)
                                or _is_public_api_package_path(
                                    file_path, package_roots
                                )
                            )
                        )
                        or runtime_plugin_workspace_heuristic_applied,
                        "runtime_plugin_config_heuristic_applied": (
                            runtime_plugin_config_heuristic_applied
                        ),
                        "runtime_plugin_entrypoint_heuristic_applied": (
                            runtime_plugin_entrypoint_heuristic_applied
                        ),
                        "runtime_plugin_workspace_heuristic_applied": (
                            runtime_plugin_workspace_heuristic_applied
                        ),
                        "published_package_heuristic_applied": (
                            published_package_heuristic_applied
                        ),
                        "published_package_name": published_package_name,
                        "testkit_contract_heuristic_applied": (
                            testkit_contract_heuristic_applied
                        ),
                        "finding_context": path_context,
                    },
                    finding_context=path_context,
                    rule_id="dead_code_accumulation",
                )
            )

        return findings

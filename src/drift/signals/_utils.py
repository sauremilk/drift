"""Shared utilities for signal implementations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from drift.ingestion.test_detection import is_test_file as _is_test_file

_TS_LANGUAGES: frozenset[str] = frozenset(
    {"typescript", "tsx", "javascript", "jsx"},
)

_SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"python"}) | _TS_LANGUAGES

_LIBRARY_ROOT_DIRS: frozenset[str] = frozenset({"src", "lib", "packages"})
_APPLICATION_ROOT_DIRS: frozenset[str] = frozenset(
    {"app", "apps", "backend", "frontend", "service", "services", "server", "web"}
)


def is_test_file(file_path: Path) -> bool:
    """Return True if *file_path* looks like a test file (by name / path).

    Covers Python, TypeScript / JavaScript and common JS test directories.
    """
    return _is_test_file(file_path)


def is_library_finding_path(file_path: Path | None) -> bool:
    """Return True when *file_path* matches common library source layouts."""
    if file_path is None:
        return False
    parts = file_path.as_posix().lower().split("/")
    if not parts:
        return False
    if any(part in _LIBRARY_ROOT_DIRS for part in parts):
        return True
    # Monorepo layout: packages/<pkg>/(src|lib)/...
    return any(
        parts[idx] == "packages" and idx + 2 < len(parts) and parts[idx + 2] in {"src", "lib"}
        for idx in range(len(parts))
    )


def is_likely_library_repo(parse_results: list[Any]) -> bool:
    """Heuristic repository profile detection for library-style layouts.

    Conservative by design: requires at least one library-style root and no
    strong application root markers.
    """
    path_tokens: set[str] = set()
    for pr in parse_results:
        file_path = getattr(pr, "file_path", None)
        if not isinstance(file_path, Path):
            continue
        if is_test_file(file_path):
            continue
        parts = file_path.as_posix().lower().split("/")
        path_tokens.update(part for part in parts if part)

    has_library_layout = any(token in _LIBRARY_ROOT_DIRS for token in path_tokens)
    has_application_layout = any(token in _APPLICATION_ROOT_DIRS for token in path_tokens)
    return has_library_layout and not has_application_layout


# ---------------------------------------------------------------------------
# Tree-sitter helpers (shared by GCD, NBV, and future TS-aware signals)
# ---------------------------------------------------------------------------


def ts_parse_source(source: str, language: str = "typescript") -> tuple[Any, bytes] | None:
    """Parse *source* with tree-sitter.  Returns ``(root_node, source_bytes)`` or *None*."""
    try:
        from drift.ingestion.ts_parser import _get_parser, tree_sitter_available

        if not tree_sitter_available():
            return None
        ts_lang = "tsx" if language in ("tsx", "jsx") else "typescript"
        parser = _get_parser(ts_lang)
        source_bytes = source.encode("utf-8")
        tree = parser.parse(source_bytes)
        return tree.root_node, source_bytes
    except ImportError:
        return None
    except Exception:
        logging.getLogger("drift").debug(
            "tree-sitter parse failed for %s source", language, exc_info=True,
        )
        return None


def ts_walk(node: Any) -> list[Any]:
    """Depth-first walk of all descendants of a tree-sitter node."""
    result: list[Any] = []
    stack = [node]
    while stack:
        n = stack.pop()
        result.append(n)
        stack.extend(reversed(n.children))
    return result


def ts_node_text(node: Any, source: bytes) -> str:
    """Extract the UTF-8 text of a tree-sitter node."""
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

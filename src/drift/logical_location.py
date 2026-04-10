"""Enrich findings with AST-based logical locations.

Central post-processing step that resolves ``(file_path, start_line)``
coordinates to structured ``LogicalLocation`` objects using the
``FunctionInfo`` / ``ClassInfo`` data already present in ``ParseResult``.

This avoids modifying each individual signal: one pipeline step resolves
all findings after signal execution.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from drift.models import ClassInfo, Finding, FunctionInfo, LogicalLocation, ParseResult


# ---------------------------------------------------------------------------
# Internal index types
# ---------------------------------------------------------------------------

# _NodeEntry: (start_line, end_line, span_size, kind, node)
# span_size is used for narrowest-match selection.
_NodeEntry = tuple[int, int, int, str, Union["FunctionInfo", "ClassInfo"]]


def _file_path_to_namespace(file_path: Path) -> str:
    """Convert a file path to a dotted module namespace.

    ``src/api/auth.py`` → ``src.api.auth``
    ``src/api/auth/__init__.py`` → ``src.api.auth``
    """
    posix = PurePosixPath(file_path)
    parts = list(posix.parts)

    # Strip .py / .pyi suffix from the last segment
    if parts and parts[-1].endswith((".py", ".pyi")):
        stem = parts[-1].rsplit(".", 1)[0]
        if stem == "__init__":
            parts = parts[:-1]
        else:
            parts[-1] = stem

    return ".".join(parts)


# ---------------------------------------------------------------------------
# Index builder
# ---------------------------------------------------------------------------


def _build_location_index(
    parse_results: list[ParseResult],
) -> dict[str, list[_NodeEntry]]:
    """Build a per-file index of (start, end, span, kind, node) entries.

    Returns a dict keyed by POSIX file path.  Each value is a list of
    entries sorted by span size ascending (narrowest first).
    """
    index: dict[str, list[_NodeEntry]] = {}

    for pr in parse_results:
        key = pr.file_path.as_posix()
        entries = index.setdefault(key, [])

        for cls in pr.classes:
            span = max(cls.end_line - cls.start_line, 0)
            entries.append((cls.start_line, cls.end_line, span, "class", cls))

            for method in cls.methods:
                method_span = max(method.end_line - method.start_line, 0)
                entries.append(
                    (method.start_line, method.end_line, method_span, "method", method),
                )

        for fn in pr.functions:
            # Skip methods already added via class traversal (they appear
            # in both pr.functions and cls.methods with class-qualified names).
            if "." in fn.name:
                continue
            span = max(fn.end_line - fn.start_line, 0)
            entries.append((fn.start_line, fn.end_line, span, "function", fn))

    # Sort each file's entries by span ascending so the narrowest match
    # comes first during lookup.
    for entries in index.values():
        entries.sort(key=lambda e: e[2])

    return index


def _resolve(
    file_path: Path,
    start_line: int | None,
    index: dict[str, list[_NodeEntry]],
) -> LogicalLocation | None:
    """Resolve a finding's location to a LogicalLocation.

    Prefers the narrowest enclosing AST node (method > class > module).
    """
    from drift.models import LogicalLocation

    key = file_path.as_posix()
    namespace = _file_path_to_namespace(file_path)

    entries = index.get(key)
    if not entries or start_line is None:
        # Module-level fallback
        stem = PurePosixPath(file_path).stem
        if stem == "__init__":
            stem = PurePosixPath(file_path).parent.name
        return LogicalLocation(
            fully_qualified_name=namespace,
            name=stem,
            kind="module",
            namespace=namespace,
        )

    # Find the narrowest enclosing node (entries are sorted by span asc).
    for node_start, node_end, _span, kind, node in entries:
        if node_start <= start_line <= node_end:
            return _node_to_location(node, kind, namespace)

    # No enclosing node — fall back to module level.
    stem = PurePosixPath(file_path).stem
    if stem == "__init__":
        stem = PurePosixPath(file_path).parent.name
    return LogicalLocation(
        fully_qualified_name=namespace,
        name=stem,
        kind="module",
        namespace=namespace,
    )


def _node_to_location(
    node: FunctionInfo | ClassInfo,
    kind: str,
    namespace: str,
) -> LogicalLocation:
    """Convert an AST node + kind to a LogicalLocation."""
    from drift.models import ClassInfo, LogicalLocation

    if isinstance(node, ClassInfo):
        fqn = f"{namespace}.{node.name}" if namespace else node.name
        return LogicalLocation(
            fully_qualified_name=fqn,
            name=node.name,
            kind="class",
            class_name=node.name,
            namespace=namespace,
        )

    # FunctionInfo — could be a method (class-qualified name) or plain function.
    raw_name = node.name
    if kind == "method" and "." in raw_name:
        class_name, method_name = raw_name.rsplit(".", 1)
        fqn = f"{namespace}.{class_name}.{method_name}" if namespace else raw_name
        return LogicalLocation(
            fully_qualified_name=fqn,
            name=method_name,
            kind="method",
            class_name=class_name,
            namespace=namespace,
        )

    # Standalone function
    fqn = f"{namespace}.{raw_name}" if namespace else raw_name
    return LogicalLocation(
        fully_qualified_name=fqn,
        name=raw_name,
        kind="function",
        namespace=namespace,
    )


# ---------------------------------------------------------------------------
# Public enrichment entry point
# ---------------------------------------------------------------------------


def enrich_logical_locations(
    findings: list[Finding],
    parse_results: list[ParseResult],
) -> None:
    """Enrich each finding with a ``logical_location`` derived from ParseResult AST data.

    Also back-fills ``finding.symbol`` when it is empty, so that existing
    consumers benefit immediately without awareness of ``logical_location``.

    Mutates findings in place.
    """
    if not parse_results:
        return

    index = _build_location_index(parse_results)

    for finding in findings:
        if finding.file_path is None:
            continue

        loc = _resolve(finding.file_path, finding.start_line, index)
        if loc is not None:
            finding.logical_location = loc

            # Back-fill symbol for existing consumers
            if not finding.symbol and loc.kind in ("function", "method", "class"):
                finding.symbol = loc.name

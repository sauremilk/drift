"""Relative TypeScript import graph builder.

Builds a directed file-level graph from static ``import`` statements in
``.ts`` and ``.tsx`` files. Relative imports (``./`` or ``../``) and
``tsconfig`` path aliases are resolved and included.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path

from drift.analyzers.typescript.alias_resolver import resolve_tsconfig_alias_import
from drift.analyzers.typescript.barrel_resolver import resolve_index_barrel_target

_IMPORT_FROM_RE = re.compile(
    r"^\s*import\s+(?:type\s+)?(.+?)\s+from\s+[\"']([^\"']+)[\"']\s*;?\s*$"
)
_IMPORT_SIDE_EFFECT_RE = re.compile(
    r"^\s*import\s+[\"']([^\"']+)[\"']\s*;?\s*$"
)

_IGNORED_PATH_PARTS = {
    "node_modules",
    "__pycache__",
    "venv",
    ".venv",
    ".git",
    "dist",
    "build",
}


@dataclass(frozen=True)
class ImportStatement:
    """Structured representation of a static import statement."""

    module_spec: str
    imported_symbols: set[str] | None


def _iter_ts_sources(repo_path: Path) -> list[Path]:
    """Return repository-relative paths for all .ts and .tsx source files."""
    def _is_ignored(path: Path) -> bool:
        return any(part in _IGNORED_PATH_PARTS for part in path.parts)

    files = [
        p.relative_to(repo_path)
        for p in repo_path.rglob("*.ts")
        if p.is_file() and not _is_ignored(p)
    ]
    files.extend(
        p.relative_to(repo_path)
        for p in repo_path.rglob("*.tsx")
        if p.is_file() and not _is_ignored(p)
    )
    return sorted(set(files), key=lambda p: p.as_posix())


def _parse_named_import_symbols(import_clause: str) -> set[str] | None:
    """Parse requested module symbols from ``import { ... } from`` clause."""
    start = import_clause.find("{")
    end = import_clause.find("}", start + 1)
    if start == -1 or end == -1:
        return None

    names: set[str] = set()
    for part in import_clause[start + 1 : end].split(","):
        token = part.strip()
        if not token:
            continue

        if token.startswith("type "):
            token = token[len("type ") :].strip()

        if " as " in token:
            requested_name, _ = token.split(" as ", 1)
            requested_name = requested_name.strip()
            if requested_name:
                names.add(requested_name)
            continue

        names.add(token)

    return names


def _extract_import_statements(source_text: str) -> list[ImportStatement]:
    """Extract module specifiers and imported symbols from static import statements."""
    statements: list[ImportStatement] = []
    for line in source_text.splitlines():
        if "import" not in line:
            continue

        from_match = _IMPORT_FROM_RE.match(line)
        if from_match:
            import_clause, module_spec = from_match.groups()
            statements.append(
                ImportStatement(
                    module_spec=module_spec,
                    imported_symbols=_parse_named_import_symbols(import_clause),
                )
            )
            continue

        side_effect_match = _IMPORT_SIDE_EFFECT_RE.match(line)
        if side_effect_match:
            statements.append(
                ImportStatement(
                    module_spec=side_effect_match.group(1),
                    imported_symbols=None,
                )
            )

    return statements


def _normalize_rel_path(path: Path) -> Path:
    """Normalize a repository-relative path using POSIX semantics."""
    return Path(posixpath.normpath(path.as_posix()))


def _resolve_relative_target(
    repo_path: Path,
    source_path: Path,
    module_spec: str,
) -> Path | None:
    """Resolve a relative TS module specifier to a repository-relative file path."""
    if not (module_spec.startswith("./") or module_spec.startswith("../")):
        return None

    base_candidate = _normalize_rel_path(source_path.parent / module_spec)

    # Explicit extension imports are accepted only for .ts and .tsx.
    if base_candidate.suffix in {".ts", ".tsx"}:
        explicit = repo_path / base_candidate
        if explicit.is_file():
            return base_candidate
        return None

    # Missing extension: prefer .ts, then .tsx.
    for suffix in (".ts", ".tsx"):
        candidate = _normalize_rel_path(Path(f"{base_candidate.as_posix()}{suffix}"))
        if (repo_path / candidate).is_file():
            return candidate

    # Directory import: resolve to index.ts or index.tsx.
    for index_name in ("index.ts", "index.tsx"):
        index_candidate = _normalize_rel_path(base_candidate / index_name)
        if (repo_path / index_candidate).is_file():
            return index_candidate

    return None


def build_relative_import_graph(repo_path: Path) -> dict[str, set[str]]:
    """Build a directed graph of resolved TypeScript imports.

    Returns:
        Mapping ``source_path -> {target_path, ...}`` where paths are
        repository-relative POSIX strings.
    """
    graph: dict[str, set[str]] = {}

    for source_path in _iter_ts_sources(repo_path):
        full_source_path = repo_path / source_path
        source_text = full_source_path.read_text(encoding="utf-8", errors="replace")
        source_key = source_path.as_posix()

        for statement in _extract_import_statements(source_text):
            target = _resolve_relative_target(repo_path, source_path, statement.module_spec)
            if target is None:
                target = resolve_tsconfig_alias_import(
                    repo_path=repo_path,
                    source_path=source_path,
                    module_spec=statement.module_spec,
                )
            if target is None:
                continue

            barrel_target = resolve_index_barrel_target(
                repo_path=repo_path,
                index_path=target,
                imported_symbols=statement.imported_symbols,
            )
            if barrel_target is not None:
                target = barrel_target

            graph.setdefault(source_key, set()).add(target.as_posix())

    return graph

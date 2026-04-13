"""Resolve TypeScript path aliases defined in tsconfig.json."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from drift.analyzers.typescript._path_utils import relative_to_or_none

_ALLOWED_EXTENSIONS = {".ts", ".tsx"}
logger = logging.getLogger("drift")


def _load_compiler_options(tsconfig_path: Path) -> dict[str, object]:
    """Load compilerOptions from tsconfig.json, returning an empty mapping on errors."""
    try:
        data = json.loads(tsconfig_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict()

    compiler_options = data.get("compilerOptions", {})
    if not isinstance(compiler_options, dict):
        return {}
    return compiler_options


def _load_tsconfig_data(tsconfig_path: Path) -> dict[str, Any] | None:
    """Load tsconfig JSON object, returning None on read/parse errors."""
    try:
        data = json.loads(tsconfig_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    return data if isinstance(data, dict) else None


def _resolve_extends_path(tsconfig_path: Path, extends_value: str) -> Path | None:
    """Resolve a local tsconfig extends reference to an existing JSON file."""
    extends_path = Path(extends_value)
    if not extends_path.is_absolute() and not extends_value.startswith("."):
        # Package-style extends (node_modules) is intentionally out of scope here.
        logger.debug(
            "Skipping non-local tsconfig extends reference '%s' in %s",
            extends_value,
            tsconfig_path.as_posix(),
        )
        return None

    if extends_path.is_absolute():
        base_candidate = extends_path
    else:
        base_candidate = tsconfig_path.parent / extends_path

    candidates = [base_candidate]
    if base_candidate.suffix != ".json":
        candidates.append(Path(f"{base_candidate.as_posix()}.json"))
    if base_candidate.suffix == "":
        candidates.append(base_candidate / "tsconfig.json")

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    return None


def _collect_tsconfig_chain(tsconfig_path: Path) -> list[Path]:
    """Collect tsconfig files from leaf to root via recursive extends."""
    chain: list[Path] = []
    visited: set[Path] = set()

    current = tsconfig_path.resolve()
    while True:
        if current in visited:
            break
        visited.add(current)
        chain.append(current)

        data = _load_tsconfig_data(current)
        if not data:
            break

        extends_value = data.get("extends")
        if not isinstance(extends_value, str):
            break

        parent = _resolve_extends_path(current, extends_value)
        if parent is None:
            break
        current = parent

    return chain


def _iter_effective_paths(tsconfig_path: Path) -> list[tuple[Path, str, list[str]]]:
    """Yield effective alias mappings with child-over-base override semantics."""
    shadowed_aliases: set[str] = set()
    mappings: list[tuple[Path, str, list[str]]] = []

    for config_path in _collect_tsconfig_chain(tsconfig_path):
        compiler_options = _load_compiler_options(config_path)
        base_url = compiler_options.get("baseUrl", ".")
        paths = compiler_options.get("paths", {})

        if not isinstance(base_url, str) or not isinstance(paths, dict):
            continue

        base_dir = config_path.parent / Path(base_url)
        for alias_pattern, target_patterns in paths.items():
            if not isinstance(alias_pattern, str) or not isinstance(target_patterns, list):
                continue
            if alias_pattern in shadowed_aliases:
                continue

            typed_targets = [item for item in target_patterns if isinstance(item, str)]
            if not typed_targets:
                shadowed_aliases.add(alias_pattern)
                continue

            mappings.append((base_dir, alias_pattern, typed_targets))
            shadowed_aliases.add(alias_pattern)

    return mappings


def _match_alias_pattern(alias_pattern: str, module_spec: str) -> str | None:
    """Return wildcard capture for matching alias pattern or None if no match."""
    if "*" not in alias_pattern:
        return "" if alias_pattern == module_spec else None

    if alias_pattern.count("*") != 1:
        return None

    prefix, suffix = alias_pattern.split("*")
    if not module_spec.startswith(prefix):
        return None
    if suffix and not module_spec.endswith(suffix):
        return None

    captured = module_spec[len(prefix) : len(module_spec) - len(suffix) if suffix else None]
    return captured


def _expand_target_pattern(target_pattern: str, wildcard_capture: str) -> str | None:
    """Expand target path pattern with wildcard capture."""
    if "*" not in target_pattern:
        return target_pattern if wildcard_capture == "" else None

    if target_pattern.count("*") != 1:
        return None

    return target_pattern.replace("*", wildcard_capture)


def _resolve_candidate_file(base_candidate: Path) -> Path | None:
    """Resolve a candidate path to an existing .ts/.tsx file."""
    if base_candidate.suffix in _ALLOWED_EXTENSIONS:
        return base_candidate if base_candidate.is_file() else None

    for suffix in (".ts", ".tsx"):
        with_suffix = Path(f"{base_candidate.as_posix()}{suffix}")
        if with_suffix.is_file():
            return with_suffix

    for index_name in ("index.ts", "index.tsx"):
        index_file = base_candidate / index_name
        if index_file.is_file():
            return index_file

    return None


def resolve_tsconfig_alias_import(
    repo_path: Path,
    source_path: Path,
    module_spec: str,
) -> Path | None:
    """Resolve a TS alias import to a repository-relative .ts/.tsx path.

    Args:
        repo_path: Repository root.
        source_path: Repository-relative source file path (reserved for API parity).
        module_spec: Import module specifier.

    Returns:
        Repository-relative target file path if resolved, otherwise None.
    """
    _ = source_path

    if module_spec.startswith("./") or module_spec.startswith("../"):
        return None

    tsconfig_path = repo_path / "tsconfig.json"
    if not tsconfig_path.is_file():
        return None

    for base_dir, alias_pattern, target_patterns in _iter_effective_paths(tsconfig_path):

        wildcard_capture = _match_alias_pattern(alias_pattern, module_spec)
        if wildcard_capture is None:
            continue

        for target_pattern in target_patterns:
            if not isinstance(target_pattern, str):
                continue

            expanded = _expand_target_pattern(target_pattern, wildcard_capture)
            if expanded is None:
                continue

            resolved = _resolve_candidate_file(base_dir / Path(expanded))
            if resolved is None:
                continue

            relative = relative_to_or_none(resolved, repo_path)
            if relative is not None:
                return relative

    return None

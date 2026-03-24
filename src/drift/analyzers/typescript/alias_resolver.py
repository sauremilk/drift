"""Resolve TypeScript path aliases defined in tsconfig.json."""

from __future__ import annotations

import json
from pathlib import Path

_ALLOWED_EXTENSIONS = {".ts", ".tsx"}


def _load_compiler_options(tsconfig_path: Path) -> dict[str, object]:
    """Load compilerOptions from tsconfig.json, returning an empty mapping on errors."""
    try:
        data = json.loads(tsconfig_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    compiler_options = data.get("compilerOptions", {})
    if not isinstance(compiler_options, dict):
        return {}
    return compiler_options


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

    compiler_options = _load_compiler_options(tsconfig_path)
    base_url = compiler_options.get("baseUrl", ".")
    paths = compiler_options.get("paths", {})

    if not isinstance(base_url, str) or not isinstance(paths, dict):
        return None

    base_dir = tsconfig_path.parent / Path(base_url)

    for alias_pattern, target_patterns in paths.items():
        if not isinstance(alias_pattern, str) or not isinstance(target_patterns, list):
            continue

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

            try:
                return resolved.relative_to(repo_path)
            except ValueError:
                continue

    return None

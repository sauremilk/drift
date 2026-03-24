"""Detect TypeScript workspace package boundaries from root package.json."""

from __future__ import annotations

import json
from pathlib import Path

_IGNORED_PATH_PARTS = {
    "node_modules",
    "__pycache__",
    "venv",
    ".venv",
    ".git",
    "dist",
    "build",
}


def _iter_ts_sources(repo_path: Path) -> list[Path]:
    """Return repository-relative .ts/.tsx sources sorted by POSIX path."""
    def _is_ignored(path: Path) -> bool:
        return any(part in _IGNORED_PATH_PARTS for part in path.parts)

    files = [
        path.relative_to(repo_path)
        for path in repo_path.rglob("*.ts")
        if path.is_file() and not _is_ignored(path)
    ]
    files.extend(
        path.relative_to(repo_path)
        for path in repo_path.rglob("*.tsx")
        if path.is_file() and not _is_ignored(path)
    )
    return sorted(set(files), key=lambda p: p.as_posix())


def _load_root_workspaces(repo_path: Path) -> list[str]:
    """Load workspace glob patterns from the root package.json only."""
    package_json_path = repo_path / "package.json"
    if not package_json_path.is_file():
        return []

    try:
        package_data = json.loads(package_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    workspaces = package_data.get("workspaces")
    if isinstance(workspaces, list):
        return [item for item in workspaces if isinstance(item, str)]

    if isinstance(workspaces, dict):
        packages = workspaces.get("packages")
        if isinstance(packages, list):
            return [item for item in packages if isinstance(item, str)]

    return []


def discover_workspace_package_roots(repo_path: Path) -> list[Path]:
    """Expand root package.json workspace globs into package root directories."""
    package_roots: set[Path] = set()

    for workspace_glob in _load_root_workspaces(repo_path):
        for match in repo_path.glob(workspace_glob):
            if match.is_dir():
                package_roots.add(match.resolve())

    normalized_roots: set[Path] = set()
    for package_root in package_roots:
        try:
            normalized_roots.add(package_root.relative_to(repo_path.resolve()))
        except ValueError:
            continue

    return sorted(normalized_roots, key=lambda p: p.as_posix())


def assign_ts_sources_to_workspace_packages(repo_path: Path) -> dict[str, str]:
    """Assign each .ts/.tsx source to exactly one workspace package root.

    Returns:
        Mapping ``source_path -> package_root`` where both paths are
        repository-relative POSIX strings.

    Raises:
        ValueError: If a source matches multiple package roots.
    """
    package_roots = discover_workspace_package_roots(repo_path)
    assignments: dict[str, str] = {}

    for source_path in _iter_ts_sources(repo_path):
        candidates: list[Path] = []
        for package_root in package_roots:
            try:
                source_path.relative_to(package_root)
            except ValueError:
                continue
            candidates.append(package_root)

        if not candidates:
            assignments[source_path.as_posix()] = "root"
            continue

        # If globs overlap, prefer the deepest root that still contains the file.
        candidates.sort(key=lambda p: len(p.parts), reverse=True)
        top_depth = len(candidates[0].parts)
        top_candidates = [
            candidate for candidate in candidates if len(candidate.parts) == top_depth
        ]
        if len(top_candidates) != 1:
            raise ValueError(
                "Multiple workspace packages for source file: "
                f"{source_path.as_posix()} -> {[c.as_posix() for c in top_candidates]}"
            )

        assignments[source_path.as_posix()] = top_candidates[0].as_posix()

    return assignments


def build_workspace_package_membership(repo_path: Path) -> dict[str, set[str]]:
    """Expose package membership as ``package_root -> {source_files}``."""
    assignments = assign_ts_sources_to_workspace_packages(repo_path)
    membership: dict[str, set[str]] = {}

    for source_path, package_root in assignments.items():
        membership.setdefault(package_root, set()).add(source_path)

    return membership

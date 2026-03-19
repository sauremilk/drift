"""File discovery and language detection."""

from __future__ import annotations

import fnmatch
import logging
from pathlib import Path

from drift.models import FileInfo

logger = logging.getLogger("drift")

LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "jsx",
}

SUPPORTED_LANGUAGES = {"python"}


def detect_language(path: Path) -> str | None:
    return LANGUAGE_MAP.get(path.suffix.lower())


def _matches_any(path_str: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path_str, pattern) for pattern in patterns)


def discover_files(
    repo_path: Path,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> list[FileInfo]:
    """Walk the repo and return all source files matching include/exclude patterns."""
    if include is None:
        include = ["**/*.py"]
    if exclude is None:
        exclude = [
            "**/node_modules/**",
            "**/__pycache__/**",
            "**/venv/**",
            "**/.venv/**",
            "**/.git/**",
            "**/dist/**",
            "**/build/**",
        ]

    files: list[FileInfo] = []
    repo_path = repo_path.resolve()

    # Max file size to analyse (5 MB) — skip generated/vendored giants
    max_bytes = 5 * 1024 * 1024

    # Pre-deuplicate: track seen paths during enumeration
    seen: set[str] = set()

    for pattern in include:
        for match in repo_path.glob(pattern):
            if not match.is_file():
                continue

            # Skip symlinks to avoid loops and double-counting
            if match.is_symlink():
                continue

            rel = match.relative_to(repo_path).as_posix()

            # Inline dedup — glob patterns can match same file
            if rel in seen:
                continue
            seen.add(rel)

            if _matches_any(rel, exclude):
                continue

            lang = detect_language(match)
            if lang is None or lang not in SUPPORTED_LANGUAGES:
                continue

            stat = match.stat()
            if stat.st_size > max_bytes:
                logger.debug(
                    "Skipping oversized file (%d bytes): %s", stat.st_size, rel
                )
                continue

            # Estimate line count from file size (avoids reading file)
            # Actual line count computed later during AST parsing
            line_count = stat.st_size // 40  # ~40 bytes/line heuristic

            files.append(
                FileInfo(
                    path=match.relative_to(repo_path),
                    language=lang,
                    size_bytes=stat.st_size,
                    line_count=line_count,
                )
            )

    return sorted(files, key=lambda f: f.path.as_posix())

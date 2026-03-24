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


def _detect_supported_languages() -> set[str]:
    """Return the set of languages supported in this environment."""
    langs = {"python"}
    try:
        from drift.ingestion.ts_parser import tree_sitter_available

        if tree_sitter_available():
            langs |= {"typescript", "tsx", "javascript", "jsx"}
    except ImportError:
        pass
    return langs


def detect_language(path: Path) -> str | None:
    return LANGUAGE_MAP.get(path.suffix.lower())


def _matches_any(path_str: str, patterns: list[str]) -> bool:
    """Check if *path_str* matches any exclude pattern.

    ``fnmatch`` treats ``*`` as "any characters except separator" but does
    **not** support ``**`` for recursive directory matching.  The common
    pattern ``**/dirname/**`` therefore never matches paths with multiple
    directory levels.  We handle this by extracting the middle segment of
    ``**/X/**`` patterns and testing it against each path component with
    ``fnmatch`` (so ``**/*.egg-info/**`` still works).
    """
    parts = path_str.split("/")
    for pattern in patterns:
        norm_pattern = pattern.replace("\\", "/")

        # Patterns without directory separators are filename globs.
        # They only apply to top-level paths; nested paths never match.
        if "/" not in norm_pattern:
            if "/" not in path_str and fnmatch.fnmatch(path_str, norm_pattern):
                return True
            continue

        if fnmatch.fnmatch(path_str, norm_pattern):
            return True
        # Recursive directory patterns: **/name/** or **/pattern/**
        if norm_pattern.startswith("**/") and norm_pattern.endswith("/**"):
            dir_pattern = norm_pattern[3:-3]  # strip **/ and /**
            for part in parts:
                if fnmatch.fnmatch(part, dir_pattern):
                    return True
    return False


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
    supported = _detect_supported_languages()
    skipped_langs: dict[str, int] = {}

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
            if lang is None:
                continue
            if lang not in supported:
                skipped_langs[lang] = skipped_langs.get(lang, 0) + 1
                continue

            stat = match.stat()
            if stat.st_size > max_bytes:
                logger.debug("Skipping oversized file (%d bytes): %s", stat.st_size, rel)
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

    if skipped_langs:
        summary = ", ".join(f"{lang} ({n})" for lang, n in sorted(skipped_langs.items()))
        logger.warning(
            "Skipped %d file(s) with unsupported languages: %s. "
            "Install tree-sitter for TypeScript/TSX support.",
            sum(skipped_langs.values()),
            summary,
        )

    return sorted(files, key=lambda f: f.path.as_posix())

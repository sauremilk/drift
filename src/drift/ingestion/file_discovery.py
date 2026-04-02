"""File discovery and language detection."""

from __future__ import annotations

import fnmatch
import logging
from functools import lru_cache
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


PreparedPattern = tuple[str, str | None, bool]


@lru_cache(maxsize=128)
def _prepare_patterns(patterns_key: tuple[str, ...]) -> tuple[PreparedPattern, ...]:
    """Normalize and precompute pattern metadata for repeated matching."""
    prepared: list[PreparedPattern] = []
    for pattern in patterns_key:
        norm_pattern = pattern.replace("\\", "/")
        top_level_only = "/" not in norm_pattern
        dir_pattern: str | None = None
        if norm_pattern.startswith("**/") and norm_pattern.endswith("/**"):
            dir_pattern = norm_pattern[3:-3]
        prepared.append((norm_pattern, dir_pattern, top_level_only))
    return tuple(prepared)


def _matches_any_prepared(path_str: str, prepared: tuple[PreparedPattern, ...]) -> bool:
    """Fast-path matcher using precomputed pattern metadata."""
    parts = path_str.split("/")
    for norm_pattern, dir_pattern, top_level_only in prepared:
        # Patterns without directory separators are filename globs.
        # They only apply to top-level paths; nested paths never match.
        if top_level_only:
            if "/" not in path_str and fnmatch.fnmatch(path_str, norm_pattern):
                return True
            continue

        if fnmatch.fnmatch(path_str, norm_pattern):
            return True

        # Recursive directory patterns: **/name/** or **/pattern/**
        if dir_pattern is not None:
            for part in parts:
                if fnmatch.fnmatch(part, dir_pattern):
                    return True
    return False


def _matches_any(path_str: str, patterns: list[str]) -> bool:
    """Check if *path_str* matches any exclude pattern.

    ``fnmatch`` treats ``*`` as "any characters except separator" but does
    **not** support ``**`` for recursive directory matching.  The common
    pattern ``**/dirname/**`` therefore never matches paths with multiple
    directory levels.  We handle this by extracting the middle segment of
    ``**/X/**`` patterns and testing it against each path component with
    ``fnmatch`` (so ``**/*.egg-info/**`` still works).
    """
    prepared = _prepare_patterns(tuple(patterns))
    return _matches_any_prepared(path_str, prepared)


def discover_files(
    repo_path: Path,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    max_files: int | None = None,
    skipped_out: dict[str, int] | None = None,
) -> list[FileInfo]:
    """Walk the repo and return all source files matching include/exclude patterns.

    Parameters
    ----------
    skipped_out:
        If a mutable dict is passed, it is populated with ``{language: count}``
        entries for files that were recognized but skipped because their
        language runtime is not installed (e.g. TypeScript without tree-sitter).
    """
    supported = _detect_supported_languages()

    if include is None:
        include = ["**/*.py"]
        if "typescript" in supported:
            include.extend(["**/*.ts", "**/*.tsx"])
    if exclude is None:
        exclude = [
            "**/node_modules/**",
            "**/__pycache__/**",
            "**/venv/**",
            "**/.venv/**",
            "**/.tmp_*venv*/**",
            "**/.env/**",
            "**/.conda/**",
            "**/.git/**",
            "**/.tox/**",
            "**/.nox/**",
            "**/dist/**",
            "**/build/**",
            "**/site-packages/**",
            "**/.pixi/**",
            "**/tests/**",
            "**/scripts/**",
        ]
    prepared_exclude = _prepare_patterns(tuple(exclude))

    files: list[FileInfo] = []
    repo_path = repo_path.resolve()

    # Max file size to analyse (5 MB) — skip generated/vendored giants
    max_bytes = 5 * 1024 * 1024

    # Pre-deuplicate: track seen paths during enumeration
    seen: set[str] = set()
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

            if _matches_any_prepared(rel, prepared_exclude):
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

            if max_files is not None and len(files) >= max_files:
                logger.warning(
                    "Reached discovery file limit (%d). Stopping enumeration.",
                    max_files,
                )
                return sorted(files, key=lambda f: f.path.as_posix())

    if skipped_langs:
        summary = ", ".join(f"{lang} ({n})" for lang, n in sorted(skipped_langs.items()))
        logger.warning(
            "Skipped %d file(s) with unsupported languages: %s. "
            "Install tree-sitter for TypeScript/TSX support.",
            sum(skipped_langs.values()),
            summary,
        )
        if skipped_out is not None:
            skipped_out.update(skipped_langs)

    return sorted(files, key=lambda f: f.path.as_posix())

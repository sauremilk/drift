"""File discovery and language detection."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import logging
import os
import subprocess
import tempfile
import time
from functools import lru_cache
from pathlib import Path, PurePosixPath
from threading import Lock
from typing import Any

from drift.models import FileInfo


def _matches_include_patterns(path_str: str, include_patterns: list[str]) -> bool:
    posix_path = PurePosixPath(path_str)
    for pattern in include_patterns:
        norm = pattern.replace("\\", "/")
        if posix_path.match(norm):
            return True
        if norm.startswith("**/") and posix_path.match(norm[3:]):
            return True
    return False


logger = logging.getLogger("drift")

LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "jsx",
}

SUPPORTED_LANGUAGES = {"python"}

_DISCOVERY_MANIFEST_VERSION = 1
_DISCOVERY_MANIFEST_FILE = "file_discovery_manifest.json"
_DISCOVERY_MANIFEST_MAX_ENTRIES = 16
_GIT_HEAD_TTL_SECONDS = 5.0
_GIT_HEAD_CACHE_LOCK = Lock()
_GIT_HEAD_CACHE: dict[str, tuple[float, str | None]] = {}


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


def _manifest_path(repo_path: Path, cache_dir: str) -> Path:
    return repo_path / cache_dir / _DISCOVERY_MANIFEST_FILE


def _load_discovery_manifest(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "version": _DISCOVERY_MANIFEST_VERSION,
            "entries": {},
        }
    if not isinstance(raw, dict):
        return {"version": _DISCOVERY_MANIFEST_VERSION, "entries": {}}
    if raw.get("version") != _DISCOVERY_MANIFEST_VERSION:
        return {"version": _DISCOVERY_MANIFEST_VERSION, "entries": {}}
    entries = raw.get("entries")
    if not isinstance(entries, dict):
        return {"version": _DISCOVERY_MANIFEST_VERSION, "entries": {}}
    return {
        "version": _DISCOVERY_MANIFEST_VERSION,
        "entries": entries,
    }


def _store_discovery_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replace keeps manifest reads consistent across interrupted writes.
    fd, tmp_name = tempfile.mkstemp(
        prefix=".discovery-manifest-",
        suffix=".json",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=True, separators=(",", ":"))
        Path(tmp_name).replace(path)
    finally:
        tmp_path = Path(tmp_name)
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _current_git_head(repo_path: Path) -> str | None:
    posix_key = repo_path.resolve().as_posix()
    now = time.monotonic()
    with _GIT_HEAD_CACHE_LOCK:
        cached = _GIT_HEAD_CACHE.get(posix_key)
        if cached is not None and (now - cached[0]) < _GIT_HEAD_TTL_SECONDS:
            return cached[1]

    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=5,
        )
    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ):
        head = None
    else:
        head = result.stdout.strip() or None

    with _GIT_HEAD_CACHE_LOCK:
        _GIT_HEAD_CACHE[posix_key] = (now, head)
    return head


def _mtime_fingerprint(
    repo_path: Path,
    include_patterns: list[str],
    prepared_exclude: tuple[PreparedPattern, ...],
    supported_languages: set[str],
) -> str:
    max_mtime_ns = 0
    candidate_count = 0
    for root, dirs, files in os.walk(repo_path):
        root_path = Path(root)
        rel_root = root_path.relative_to(repo_path).as_posix()
        pruned_dirs: list[str] = []
        for d in dirs:
            rel_dir = f"{rel_root}/{d}" if rel_root != "." else d
            if _matches_any_prepared(rel_dir, prepared_exclude):
                continue
            pruned_dirs.append(d)
        dirs[:] = pruned_dirs

        for file_name in files:
            file_path = root_path / file_name
            rel = file_path.relative_to(repo_path).as_posix()
            if _matches_any_prepared(rel, prepared_exclude):
                continue
            if not _matches_include_patterns(rel, include_patterns):
                continue
            lang = detect_language(file_path)
            if lang is None or lang not in supported_languages:
                continue
            try:
                mtime_ns = os.stat(file_path, follow_symlinks=False).st_mtime_ns
            except OSError:
                continue
            candidate_count += 1
            if mtime_ns > max_mtime_ns:
                max_mtime_ns = mtime_ns
    return f"mtime:{candidate_count}:{max_mtime_ns}"


def _cache_key(
    repo_path: Path,
    include_patterns: list[str],
    exclude_patterns: list[str],
    max_files: int | None,
    ts_enabled: bool,
    supported_languages: set[str],
) -> str:
    payload = {
        "repo": repo_path.resolve().as_posix(),
        "include": include_patterns,
        "exclude": exclude_patterns,
        "max_files": max_files,
        "ts_enabled": ts_enabled,
        "supported": sorted(supported_languages),
        "version": _DISCOVERY_MANIFEST_VERSION,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _deserialize_files(items: list[dict[str, Any]]) -> list[FileInfo]:
    out: list[FileInfo] = []
    for item in items:
        try:
            out.append(
                FileInfo(
                    path=Path(item["path"]),
                    language=str(item["language"]),
                    size_bytes=int(item["size_bytes"]),
                    line_count=int(item["line_count"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _serialize_files(files: list[FileInfo]) -> list[dict[str, Any]]:
    return [
        {
            "path": file.path.as_posix(),
            "language": file.language,
            "size_bytes": file.size_bytes,
            "line_count": file.line_count,
        }
        for file in files
    ]


def discover_files(
    repo_path: Path,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    max_files: int | None = None,
    skipped_out: dict[str, int] | None = None,
    ts_enabled: bool = True,
    cache_dir: str = ".drift-cache",
) -> list[FileInfo]:
    """Walk the repo and return all source files matching include/exclude patterns.

    Parameters
    ----------
    skipped_out:
        If a mutable dict is passed, it is populated with ``{language: count}``
        entries for files that were recognized but skipped because their
        language runtime is not installed (e.g. TypeScript without tree-sitter).
    ts_enabled:
        When *False*, TypeScript/TSX/JS/JSX files are excluded from discovery
        even when tree-sitter is installed.  Controlled via
        ``drift.yaml → languages.typescript: false``.
    """
    supported = _detect_supported_languages()
    if not ts_enabled:
        supported.discard("typescript")

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
            "**/benchmarks/**",
            "**/benchmark_results/**",
            "**/tests/**",
            "**/scripts/**",
        ]
    prepared_exclude = _prepare_patterns(tuple(exclude))
    include_patterns = list(dict.fromkeys(include))

    repo_path = repo_path.resolve()

    cache_key = _cache_key(
        repo_path,
        include_patterns,
        exclude,
        max_files,
        ts_enabled,
        supported,
    )
    invalidator_type = "git_head"
    invalidator_value = _current_git_head(repo_path)
    if invalidator_value is None:
        invalidator_type = "mtime"
        invalidator_value = _mtime_fingerprint(
            repo_path,
            include_patterns,
            prepared_exclude,
            supported,
        )

    manifest_file = _manifest_path(repo_path, cache_dir)
    manifest = _load_discovery_manifest(manifest_file)
    entry = manifest.get("entries", {}).get(cache_key)
    if isinstance(entry, dict):
        entry_invalidator = entry.get("invalidator")
        if (
            isinstance(entry_invalidator, dict)
            and entry_invalidator.get("type") == invalidator_type
            and entry_invalidator.get("value") == invalidator_value
        ):
            cached_items = entry.get("files")
            if isinstance(cached_items, list):
                cached_files = _deserialize_files(cached_items)
                return cached_files

    files: list[FileInfo] = []

    # Max file size to analyse (5 MB) — skip generated/vendored giants
    max_bytes = 5 * 1024 * 1024

    # Pre-deuplicate: track seen paths during enumeration
    seen: set[str] = set()
    skipped_langs: dict[str, int] = {}

    for pattern in include_patterns:
        try:
            matches = repo_path.glob(pattern)
        except (OSError, ValueError) as exc:
            logger.warning("glob(%s) failed: %s", pattern, exc)
            continue
        for match in matches:
            try:
                if not match.is_file():
                    continue

                # Skip symlinks to avoid loops and double-counting
                if match.is_symlink():
                    continue
            except OSError:
                continue

            rel_path = match.relative_to(repo_path)
            rel = rel_path.as_posix()

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

            try:
                stat = match.stat()
            except OSError:
                logger.debug("stat() failed, skipping: %s", rel)
                continue
            if stat.st_size > max_bytes:
                logger.debug("Skipping oversized file (%d bytes): %s", stat.st_size, rel)
                continue

            # Estimate line count from file size (avoids reading file)
            # Actual line count computed later during AST parsing
            line_count = stat.st_size // 40  # ~40 bytes/line heuristic

            files.append(
                FileInfo(
                    path=rel_path,
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

    files = sorted(files, key=lambda f: f.path.as_posix())

    entries = manifest.setdefault("entries", {})
    if isinstance(entries, dict):
        entries[cache_key] = {
            "created_at": int(time.time()),
            "invalidator": {
                "type": invalidator_type,
                "value": invalidator_value,
            },
            "files": _serialize_files(files),
        }
        if len(entries) > _DISCOVERY_MANIFEST_MAX_ENTRIES:
            sorted_items = sorted(
                entries.items(),
                key=lambda item: (
                    int(item[1].get("created_at", 0))
                    if isinstance(item[1], dict)
                    else 0
                ),
                reverse=True,
            )
            manifest["entries"] = {
                key: value for key, value in sorted_items[:_DISCOVERY_MANIFEST_MAX_ENTRIES]
            }
        try:
            _store_discovery_manifest(manifest_file, manifest)
        except OSError:
            logger.debug("Unable to persist discovery manifest: %s", manifest_file)

    return files

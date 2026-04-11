"""Git blame integration for causal attribution (ADR-034).

Provides line-level provenance via ``git blame --porcelain`` to identify
which commit, author, and date introduced specific code lines.  Results
are cached per ``(file_path, content_hash)`` to avoid redundant subprocess
calls across findings in the same file.
"""

from __future__ import annotations

import contextlib
import datetime
import hashlib
import logging
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from drift.models import BlameLine

logger = logging.getLogger("drift")

# ---------------------------------------------------------------------------
# Porcelain Parser
# ---------------------------------------------------------------------------

_MERGE_BRANCH_RE = re.compile(
    r"Merge (?:pull request .+? from .+?/|branch '?)(\S+)",
    re.IGNORECASE,
)


def _parse_porcelain(raw: str) -> list[BlameLine]:
    """Parse ``git blame --porcelain`` output into BlameLine objects.

    The porcelain format emits blocks of the form::

        <40-hex commit> <orig-line> <final-line> [<num-lines>]
        author <name>
        author-mail <<email>>
        author-time <unix-ts>
        ...
        \t<content line>

    We extract commit, author, email, date, line number, and content.
    """
    lines: list[BlameLine] = []
    if not raw.strip():
        return lines

    commit_hash = ""
    author = ""
    email = ""
    date = datetime.date.today()
    line_no = 0

    for raw_line in raw.splitlines():
        # Header line: 40-hex hash followed by line numbers
        if len(raw_line) >= 40 and raw_line[0] not in ("\t", " "):
            parts = raw_line.split()
            if len(parts) >= 3 and len(parts[0]) == 40:
                commit_hash = parts[0]
                with contextlib.suppress(ValueError, IndexError):
                    line_no = int(parts[2])
        elif raw_line.startswith("author "):
            author = raw_line[7:]
        elif raw_line.startswith("author-mail "):
            # Strip angle brackets: "<user@example.com>" -> "user@example.com"
            email = raw_line[12:].strip("<>")
        elif raw_line.startswith("author-time "):
            try:
                ts = int(raw_line[12:])
                date = datetime.date.fromtimestamp(ts)
            except (ValueError, OSError):
                pass
        elif raw_line.startswith("\t"):
            # Content line terminates the block
            content = raw_line[1:]
            lines.append(
                BlameLine(
                    line_no=line_no,
                    commit_hash=commit_hash,
                    author=author,
                    email=email,
                    date=date,
                    content=content,
                )
            )

    return lines


# ---------------------------------------------------------------------------
# Blame Execution
# ---------------------------------------------------------------------------


def blame_lines(
    repo_path: Path,
    file_path: str,
    start_line: int | None = None,
    end_line: int | None = None,
    *,
    timeout: float = 3.0,
) -> list[BlameLine]:
    """Run ``git blame --porcelain`` for a file or line range.

    Args:
        repo_path: Repository root path.
        file_path: POSIX-style path relative to repo root.
        start_line: First line to blame (1-based, inclusive).
        end_line: Last line to blame (1-based, inclusive).
        timeout: Maximum seconds for the subprocess call.

    Returns:
        List of :class:`BlameLine` — one per line in the range.
        Empty list on error or timeout (never raises).
    """
    cmd = ["git", "blame", "--porcelain"]
    if start_line is not None:
        end = end_line if end_line is not None else start_line
        cmd.append(f"-L{start_line},{end}")
    cmd.append("--")
    cmd.append(file_path)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(repo_path),
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.debug("git blame timed out or unavailable for %s", file_path)
        return []
    except OSError:
        logger.debug("git blame OS error for %s", file_path)
        return []

    if result.returncode != 0:
        logger.debug("git blame failed (rc=%d) for %s", result.returncode, file_path)
        return []

    return _parse_porcelain(result.stdout)


# ---------------------------------------------------------------------------
# Blame Cache (in-memory, keyed by file + content hash)
# ---------------------------------------------------------------------------


def _content_hash(repo_path: Path, file_path: str) -> str | None:
    """Compute SHA-256 of file content for cache key."""
    full = repo_path / file_path
    try:
        data = full.read_bytes()
        return hashlib.sha256(data).hexdigest()[:16]
    except OSError:
        return None


class BlameCache:
    """In-memory LRU-ish cache for blame results, keyed by file content hash."""

    def __init__(self, max_size: int = 500) -> None:
        self._store: dict[str, list[BlameLine]] = {}
        self._max_size = max_size

    def get(self, key: str) -> list[BlameLine] | None:
        return self._store.get(key)

    def put(self, key: str, value: list[BlameLine]) -> None:
        if len(self._store) >= self._max_size:
            # Evict oldest entry (FIFO)
            oldest = next(iter(self._store))
            del self._store[oldest]
        self._store[key] = value


# ---------------------------------------------------------------------------
# Batch Blame (parallel, deduplicated by file)
# ---------------------------------------------------------------------------


def blame_files_parallel(
    repo_path: Path,
    file_requests: list[tuple[str, int | None, int | None]],
    *,
    timeout_per_file: float = 3.0,
    max_workers: int = 4,
    cache: BlameCache | None = None,
) -> dict[str, list[BlameLine]]:
    """Run blame for multiple files in parallel, deduplicating by file path.

    Args:
        repo_path: Repository root.
        file_requests: List of ``(file_path, start_line, end_line)`` tuples.
        timeout_per_file: Per-file subprocess timeout.
        max_workers: Thread pool size.
        cache: Optional BlameCache instance.

    Returns:
        Dict mapping file_path → list of BlameLine.
    """
    if cache is None:
        cache = BlameCache()

    # Deduplicate: group requests by file. For each file, use the widest
    # line range (or full file if any request omits lines).
    file_ranges: dict[str, tuple[int | None, int | None]] = {}
    for fpath, start, end in file_requests:
        existing = file_ranges.get(fpath)
        if existing is None:
            file_ranges[fpath] = (start, end)
        else:
            # Widen range: if either request has no start_line, blame full file
            if existing[0] is None or start is None:
                file_ranges[fpath] = (None, None)
            else:
                file_ranges[fpath] = (
                    min(existing[0], start),
                    max(existing[1] or start, end or start),
                )

    results: dict[str, list[BlameLine]] = {}

    # Check cache first
    uncached: dict[str, tuple[int | None, int | None]] = {}
    for fpath, (start, end) in file_ranges.items():
        chash = _content_hash(repo_path, fpath)
        if chash is not None:
            cached = cache.get(chash)
            if cached is not None:
                results[fpath] = cached
                continue
        uncached[fpath] = (start, end)

    if not uncached:
        return results

    def _blame_one(fpath: str, start: int | None, end: int | None) -> tuple[str, list[BlameLine]]:
        bl = blame_lines(repo_path, fpath, start, end, timeout=timeout_per_file)
        # Cache result
        chash = _content_hash(repo_path, fpath)
        if chash is not None:
            cache.put(chash, bl)
        return fpath, bl

    with ThreadPoolExecutor(max_workers=min(max_workers, len(uncached))) as pool:
        futures = {
            pool.submit(_blame_one, fp, s, e): fp for fp, (s, e) in uncached.items()
        }
        for future in as_completed(futures):
            try:
                fpath, blame_result = future.result()
                results[fpath] = blame_result
            except Exception:
                fpath = futures[future]
                logger.debug("blame worker failed for %s", fpath, exc_info=True)
                results[fpath] = []

    return results


def extract_branch_hint(
    repo_path: Path,
    commit_hash: str,
    *,
    timeout: float = 3.0,
) -> str | None:
    """Attempt to extract a branch name from a merge commit message.

    Looks for patterns like ``Merge branch 'feature/xxx'`` or
    ``Merge pull request #N from org/branch`` in the commit or its
    parent merge commits.
    """
    try:
        result = subprocess.run(
            ["git", "log", "--merges", "--ancestry-path",
             f"{commit_hash}..HEAD", "--format=%s", "-5"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(repo_path),
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None

    if result.returncode != 0:
        return None

    for line in result.stdout.strip().splitlines():
        m = _MERGE_BRANCH_RE.search(line)
        if m:
            return m.group(1).strip("'\"")
    return None

"""ADR scanner — finds Architecture Decision Records relevant to a task scope.

Scans ``decisions/*.md`` files in a repository, parses their YAML frontmatter
using stdlib-only regex (no pyyaml dependency), and returns ADRs that are:

1. Active: ``status`` in ``{"accepted", "proposed"}``
2. Relevant: at least one path token from *scope_paths* or keyword from *task*
   appears in the first 500 characters of the file content.

If both *scope_paths* and *task* are empty/falsy, all active ADRs are returned.
"""

from __future__ import annotations

import re
from pathlib import Path

# Active statuses — rejected/obsolete/superseded are excluded
_ACTIVE_STATUSES: frozenset[str] = frozenset({"accepted", "proposed"})

# Regex patterns for frontmatter extraction
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_KEY_VALUE_RE = re.compile(r"^(\w[\w-]*):\s*(.*)$", re.MULTILINE)
_HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _parse_frontmatter(content: str) -> dict[str, str]:
    """Extract key-value pairs from the YAML frontmatter block."""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}
    block = match.group(1)
    result: dict[str, str] = {}
    for m in _KEY_VALUE_RE.finditer(block):
        key = m.group(1).strip()
        value = m.group(2).strip()
        if key and value:
            result[key] = value
    return result


def _extract_title(content: str) -> str:
    """Extract the first top-level heading from the document."""
    match = _HEADING_RE.search(content)
    if match:
        return match.group(1).strip()
    return ""


def _is_relevant(content: str, scope_paths: list[str], task: str) -> tuple[bool, str]:
    """Return (is_relevant, reason) based on scope_paths and task keywords.

    Relevance window: first 500 characters of content (case-insensitive).
    Returns True (with no match reason set) when both scope_paths and task
    are empty — i.e. all active ADRs are considered relevant by default.
    """
    if not scope_paths and not task:
        return True, "no_filter"

    snippet = content[:500].lower()

    for path in scope_paths:
        token = path.replace("\\", "/").rstrip("/")
        parts = [p for p in token.split("/") if p]

        # Prefer multi-component suffixes (more specific, avoids false positives
        # where a single layer name appears in unrelated ADR context)
        for length in range(len(parts), 1, -1):
            suffix = "/".join(parts[-length:]).lower()
            if suffix in snippet:
                return True, f"path_token:{suffix}"

        # Single-component fallback — only for clearly distinctive tokens (>= 7 chars)
        if parts:
            last = parts[-1].lower()
            if len(last) >= 7 and last in snippet:
                return True, f"path_token:{last}"

    if task:
        # Split task into words, skip short stop-words
        words = [w.lower().strip(".,!?") for w in task.split() if len(w) >= 4]
        for word in words:
            if word in snippet:
                return True, f"task_keyword:{word}"

    return False, ""


def scan_active_adrs(
    repo_root: str | Path,
    *,
    scope_paths: list[str],
    task: str,
    max_results: int = 5,
) -> list[dict[str, str]]:
    """Return active ADRs relevant to the given scope and task.

    Parameters
    ----------
    repo_root:
        Root of the repository. The function looks for ``decisions/*.md``.
    scope_paths:
        List of file/directory paths in scope (e.g. from ``brief`` scope
        resolver). Used for content-based relevance matching.
    task:
        Natural-language task description. Keywords are matched against the
        first 500 characters of each ADR.
    max_results:
        Maximum number of ADRs to return.

    Returns
    -------
    List of dicts with keys: ``id``, ``title``, ``status``,
    ``scope_match_reason``.
    """
    root = Path(repo_root)
    decisions_dir = root / "decisions"

    if not decisions_dir.is_dir():
        return []

    results: list[dict[str, str]] = []

    for md_file in sorted(decisions_dir.glob("*.md")):
        try:
            content = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        frontmatter = _parse_frontmatter(content)

        adr_id = frontmatter.get("id", "")
        status = frontmatter.get("status", "").lower()

        if status not in _ACTIVE_STATUSES:
            continue

        relevant, reason = _is_relevant(content, scope_paths, task)
        if not relevant:
            continue

        title = _extract_title(content)

        results.append(
            {
                "id": adr_id,
                "title": title,
                "status": status,
                "scope_match_reason": reason,
            }
        )

        if len(results) >= max_results:
            break

    return results

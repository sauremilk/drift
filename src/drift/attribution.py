"""Causal attribution enrichment pipeline (ADR-034).

Enriches findings with git-blame provenance data identifying *who*
introduced the drifting code and *when*.  Runs as a post-detection
phase — after signals have produced findings and before output rendering.
"""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

from drift.config import AttributionConfig
from drift.ingestion.git_blame import (
    BlameCache,
    blame_files_parallel,
    extract_branch_hint,
)
from drift.models import Attribution, BlameLine, CommitInfo, Finding

logger = logging.getLogger("drift")


def _primary_author(blame_lines: list[BlameLine]) -> BlameLine | None:
    """Determine the primary (most frequent) author from blame lines."""
    if not blame_lines:
        return None
    # Count by (author, email) tuple
    counter: Counter[tuple[str, str]] = Counter()
    first_seen: dict[tuple[str, str], BlameLine] = {}
    for bl in blame_lines:
        key = (bl.author, bl.email)
        counter[key] += 1
        if key not in first_seen:
            first_seen[key] = bl
    most_common = counter.most_common(1)[0][0]
    return first_seen[most_common]


def _find_commit_info(
    commit_hash: str,
    commits: list[CommitInfo],
) -> CommitInfo | None:
    """Look up a CommitInfo by hash prefix (fast linear scan)."""
    for c in commits:
        if c.hash.startswith(commit_hash[:8]):
            return c
    return None


def enrich_findings(
    findings: list[Finding],
    repo_path: Path,
    config: AttributionConfig,
    commits: list[CommitInfo] | None = None,
) -> list[Finding]:
    """Enrich findings with causal attribution from git blame.

    For each finding with a ``file_path`` and ``start_line``, runs
    ``git blame`` to identify the primary author/commit that introduced
    the code.  Findings without location data are left unchanged.

    Args:
        findings: The signal-generated findings to enrich.
        repo_path: Repository root path.
        config: Attribution configuration.
        commits: Optional commit list for AI-attribution cross-reference.

    Returns:
        The same list of findings, now with ``attribution`` populated
        where blame data was available.
    """
    if not config.enabled:
        return findings

    # Collect blame requests — only for findings with file + line info
    file_requests: list[tuple[str, int | None, int | None]] = []
    finding_file_map: list[tuple[int, str]] = []  # (finding_index, file_path_posix)

    for i, f in enumerate(findings):
        if f.file_path is None or f.start_line is None:
            continue
        fpath = f.file_path.as_posix()
        file_requests.append((fpath, f.start_line, f.end_line))
        finding_file_map.append((i, fpath))

    if not file_requests:
        return findings

    # Run blame in parallel
    cache = BlameCache()
    blame_results = blame_files_parallel(
        repo_path,
        file_requests,
        timeout_per_file=config.timeout_per_file_seconds,
        max_workers=config.max_parallel_workers,
        cache=cache,
    )

    # Build commit lookup for AI attribution cross-reference
    commits = commits or []

    # Enrich each finding
    for idx, fpath in finding_file_map:
        finding = findings[idx]
        all_blame = blame_results.get(fpath, [])
        if not all_blame:
            continue

        # Filter blame lines to the finding's line range
        start = finding.start_line or 1
        end = finding.end_line or start
        relevant = [bl for bl in all_blame if start <= bl.line_no <= end]
        if not relevant:
            # Fallback to all blame lines if range filtering yields nothing
            relevant = all_blame

        primary = _primary_author(relevant)
        if primary is None:
            continue

        # Cross-reference with commit list for AI attribution
        ci = _find_commit_info(primary.commit_hash, commits)
        ai_attributed = ci.is_ai_attributed if ci else False
        ai_confidence = ci.ai_confidence if ci else 0.0
        msg_summary = (ci.message.split("\n", 1)[0][:80] if ci else "")

        # Branch hint (optional, best-effort)
        branch_hint = None
        if config.include_branch_hint:
            branch_hint = extract_branch_hint(
                repo_path,
                primary.commit_hash,
                timeout=config.timeout_per_file_seconds,
            )

        finding.attribution = Attribution(
            commit_hash=primary.commit_hash,
            author=primary.author,
            email=primary.email,
            date=primary.date,
            branch_hint=branch_hint,
            ai_attributed=ai_attributed,
            ai_confidence=ai_confidence,
            commit_message_summary=msg_summary,
        )

    enriched = sum(1 for f in findings if f.attribution is not None)
    logger.info(
        "Attribution enrichment: %d/%d findings attributed",
        enriched,
        len(findings),
    )

    return findings

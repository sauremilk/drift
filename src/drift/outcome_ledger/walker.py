"""Merge-Commit-Enumeration via git log (ADR-088)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from drift.ingestion.git_history import _detect_ai_attribution
from drift.outcome_ledger._models import AuthorType


@dataclass(frozen=True, slots=True)
class MergeCandidate:
    merge_sha: str
    parent_sha: str
    timestamp: str
    subject: str
    author_type: AuthorType
    ai_confidence: float


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout


_FIELD_SEP = "\x1f"
_RECORD_SEP = "\x1e"
_FORMAT = _FIELD_SEP.join(["%H", "%P", "%cI", "%s", "%B"]) + _RECORD_SEP


def walk_recent_merges(
    repo_path: Path,
    *,
    limit: int = 50,
    since_days: int = 180,
) -> list[MergeCandidate]:
    args = [
        "log",
        "--merges",
        "--first-parent",
        f"-n{int(limit)}",
        f"--pretty=format:{_FORMAT}",
    ]
    if since_days > 0:
        args.insert(1, f"--since={int(since_days)}.days.ago")

    raw = _run_git(repo_path, *args)
    out: list[MergeCandidate] = []
    for record in raw.split(_RECORD_SEP):
        record = record.strip("\n")
        if not record:
            continue
        parts = record.split(_FIELD_SEP)
        if len(parts) < 5:
            continue
        merge_sha, parents_raw, timestamp, subject, body = parts
        parents = parents_raw.split()
        if not parents:
            continue
        parent_sha = parents[0]

        coauthors: list[str] = []
        for line in body.splitlines():
            low = line.strip().lower()
            if low.startswith("co-authored-by:"):
                coauthors.append(line.split(":", 1)[1].strip())

        is_ai, ai_conf = _detect_ai_attribution(body or subject, coauthors)
        author_type = _classify_author(is_ai, ai_conf, coauthors)

        out.append(
            MergeCandidate(
                merge_sha=merge_sha,
                parent_sha=parent_sha,
                timestamp=timestamp,
                subject=subject,
                author_type=author_type,
                ai_confidence=float(ai_conf),
            )
        )
    return out


def _classify_author(
    is_ai: bool, ai_confidence: float, coauthors: list[str]
) -> AuthorType:
    if is_ai and ai_confidence >= 0.9 and not coauthors:
        return AuthorType.AI
    if is_ai or ai_confidence >= 0.4:
        return AuthorType.MIXED
    return AuthorType.HUMAN


__all__ = ["MergeCandidate", "walk_recent_merges"]

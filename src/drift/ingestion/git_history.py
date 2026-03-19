"""Git history analysis and AI-code attribution heuristics."""

from __future__ import annotations

import datetime
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from drift.models import CommitInfo, FileHistory

if TYPE_CHECKING:
    import git as gitmodule

# ---------------------------------------------------------------------------
# AI Attribution Heuristics
# ---------------------------------------------------------------------------

CO_AUTHOR_RE = re.compile(r"Co-authored-by:\s*(.+?)(?:\s*<(.+?)>)?\s*$", re.MULTILINE)

AI_COAUTHOR_MARKERS = [
    "copilot",
    "cursor",
    "codeium",
    "tabnine",
    "ghostwriter",
    "ai assistant",
    "github-actions",
    "anthropic",
    "openai",
]

# Commit messages dominated by AI tools tend to be formulaic.
# Require verb + at least two more words to avoid false positives on
# normal human messages like "Fix typo" or "Add tests".
AI_MESSAGE_PATTERNS = [
    re.compile(
        r"^(Add|Update|Fix|Implement|Refactor|Create|Remove) \w+ \w+", re.IGNORECASE
    ),
]

DEFECT_MARKERS = re.compile(
    r"\b(fix|bug|hotfix|revert|patch|regression|broken|crash|error)\b", re.IGNORECASE
)


def _detect_ai_attribution(message: str, coauthors: list[str]) -> tuple[bool, float]:
    """Determine if a commit is likely AI-attributed.

    Returns (is_ai, confidence) where confidence is 0.0-1.0.
    """
    # Strong signal: co-author tag from known AI tool
    for coauthor in coauthors:
        lower = coauthor.lower()
        for marker in AI_COAUTHOR_MARKERS:
            if marker in lower:
                return True, 0.95

    # Weak signal: formulaic commit message (common in AI-assisted workflows)
    msg_first_line = message.split("\n")[0].strip()
    msg_body = message.split("\n", 1)[1].strip() if "\n" in message else ""
    formulaic_match = any(p.match(msg_first_line) for p in AI_MESSAGE_PATTERNS)

    # Formulaic subject with no body and short length — likely AI-generated
    if formulaic_match and len(msg_first_line) < 60 and not msg_body:
        return True, 0.25

    return False, 0.0


def _is_defect_correlated(message: str) -> bool:
    return bool(DEFECT_MARKERS.search(message))


# ---------------------------------------------------------------------------
# Git History Parser
# ---------------------------------------------------------------------------


@dataclass
class _BulkCommitData:
    """Aggregated per-commit data from bulk git log."""

    files: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0


def _bulk_commit_files(
    repo: "gitmodule.Repo", since_iso: str
) -> dict[str, _BulkCommitData]:
    """Fetch changed-file lists and stat data for all commits since *since_iso*.

    Uses ``--numstat`` to capture per-file insertions/deletions in a single
    subprocess call, replacing the old per-commit ``commit.stats.files``.
    """
    try:
        raw: str = repo.git.log(
            "--since",
            since_iso,
            "--numstat",
            "--pretty=format:%H",
        )
    except Exception:
        return {}

    result: dict[str, _BulkCommitData] = {}
    current_hash: str | None = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # 40-char hex → commit hash
        if len(line) == 40 and all(c in "0123456789abcdef" for c in line):
            current_hash = line[:12]
            result.setdefault(current_hash, _BulkCommitData())
        elif current_hash is not None:
            # --numstat format: "insertions\tdeletions\tfilename"
            parts = line.split("\t")
            if len(parts) == 3:
                ins_str, del_str, filepath = parts
                result[current_hash].files.append(filepath)
                # Binary files show '-' instead of numbers
                if ins_str != "-":
                    result[current_hash].insertions += int(ins_str)
                if del_str != "-":
                    result[current_hash].deletions += int(del_str)
            else:
                # Fallback: plain filename (shouldn't happen with --numstat)
                result[current_hash].files.append(line)
    return result


def parse_git_history(
    repo_path: Path,
    since_days: int = 90,
    file_filter: set[str] | None = None,
) -> list[CommitInfo]:
    """Parse git history and return enriched commit information."""
    try:
        import git
    except ImportError:
        return []

    try:
        repo = git.Repo(repo_path, search_parent_directories=True)
    except (git.InvalidGitRepositoryError, git.NoSuchPathError):
        return []

    since_date = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(
        days=since_days
    )
    since_iso = since_date.isoformat()

    # Fetch all changed files in a single subprocess call
    bulk_files = _bulk_commit_files(repo, since_iso)

    commits: list[CommitInfo] = []

    try:
        commit_iter = repo.iter_commits(since=since_iso)
    except ValueError:
        # Empty repository (no commits yet)
        return []

    for commit in commit_iter:
        short_hash = commit.hexsha[:12]
        bulk_data = bulk_files.get(short_hash)
        files = bulk_data.files if bulk_data else []

        if file_filter and not any(f in file_filter for f in files):
            continue

        coauthors_raw = CO_AUTHOR_RE.findall(commit.message)
        coauthors = [name for name, _email in coauthors_raw]

        is_ai, ai_conf = _detect_ai_attribution(commit.message, coauthors)

        info = CommitInfo(
            hash=short_hash,
            author=commit.author.name or "unknown",
            email=commit.author.email or "",
            timestamp=commit.authored_datetime,
            message=commit.message.strip(),
            files_changed=files,
            insertions=bulk_data.insertions if bulk_data else 0,
            deletions=bulk_data.deletions if bulk_data else 0,
            is_ai_attributed=is_ai,
            ai_confidence=ai_conf,
            coauthors=coauthors,
        )
        commits.append(info)

    return commits


def build_file_histories(
    commits: list[CommitInfo],
    known_files: set[str] | None = None,
) -> dict[str, FileHistory]:
    """Aggregate commit data into per-file history statistics."""
    file_commits: dict[str, list[CommitInfo]] = defaultdict(list)

    for commit in commits:
        for fpath in commit.files_changed:
            if known_files and fpath not in known_files:
                continue
            file_commits[fpath].append(commit)

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    thirty_days_ago = now - datetime.timedelta(days=30)

    histories: dict[str, FileHistory] = {}

    for fpath, fcommits in file_commits.items():
        authors = {c.author for c in fcommits}
        ai_commits = [c for c in fcommits if c.is_ai_attributed]
        recent = [
            c
            for c in fcommits
            if c.timestamp.astimezone(datetime.timezone.utc) > thirty_days_ago
        ]
        defect_commits = [c for c in fcommits if _is_defect_correlated(c.message)]
        timestamps = [c.timestamp for c in fcommits]

        histories[fpath] = FileHistory(
            path=Path(fpath),
            total_commits=len(fcommits),
            unique_authors=len(authors),
            ai_attributed_commits=len(ai_commits),
            change_frequency_30d=len(recent) / max(1, 30) * 7,  # changes per week
            defect_correlated_commits=len(defect_commits),
            last_modified=max(timestamps) if timestamps else None,
            first_seen=min(timestamps) if timestamps else None,
        )

    return histories

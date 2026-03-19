"""Git history analysis and AI-code attribution heuristics."""

from __future__ import annotations

import datetime
import logging
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from drift.models import CommitInfo, FileHistory

logger = logging.getLogger("drift")

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
# We use multiple tiers of patterns with different confidence levels.
# Tier 1 (higher confidence): very specific AI-tool patterns
# Tier 2 (lower confidence): generic "Verb + noun + noun" only when
#   combined with other weak signals (no body, exact format).

# High-confidence patterns: clearly auto-generated messages
_AI_MSG_TIER1 = [
    # Cursor / Copilot default messages
    re.compile(r"^(Implement|Refactor|Create) \w+ \w+ \w+", re.IGNORECASE),
    # "Add X functionality for Y" — 4+ word noun-phrase after verb
    re.compile(
        r"^(Add|Implement|Create) \w+ \w+ (functionality|feature|support|handling|endpoint|module)\b",
        re.IGNORECASE,
    ),
]

# Low-confidence patterns: common in AI but also in humans
_AI_MSG_TIER2 = [
    re.compile(r"^(Add|Update|Fix|Remove) \w+ \w+", re.IGNORECASE),
]

DEFECT_MARKERS = re.compile(
    r"\b(fix|bug|hotfix|revert|patch|regression|broken|crash|error)\b", re.IGNORECASE
)


def _detect_ai_attribution(message: str, coauthors: list[str]) -> tuple[bool, float]:
    """Determine if a commit is likely AI-attributed.

    Returns (is_ai, confidence) where confidence is 0.0-1.0.

    Uses tiered heuristics:
    - Co-author tag from known AI tool → 0.95 confidence
    - Tier 1 formulaic message (specific AI patterns) → 0.40 confidence
    - Tier 2 formulaic message (generic verb-noun) → 0.15 confidence
      (below the default threshold, so treated as human unless
       combined with other evidence in the caller)
    """
    # Strong signal: co-author tag from known AI tool
    for coauthor in coauthors:
        lower = coauthor.lower()
        for marker in AI_COAUTHOR_MARKERS:
            if marker in lower:
                return True, 0.95

    msg_first_line = message.split("\n")[0].strip()
    msg_body = message.split("\n", 1)[1].strip() if "\n" in message else ""

    # Tier 1: specific AI patterns — higher confidence
    tier1_match = any(p.match(msg_first_line) for p in _AI_MSG_TIER1)
    if tier1_match and len(msg_first_line) < 72 and not msg_body:
        return True, 0.40

    # Tier 2: generic verb-noun patterns — only weak signal
    tier2_match = any(p.match(msg_first_line) for p in _AI_MSG_TIER2)
    if tier2_match and len(msg_first_line) < 50 and not msg_body:
        return False, 0.15

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


def parse_git_history(
    repo_path: Path,
    since_days: int = 90,
    file_filter: set[str] | None = None,
) -> list[CommitInfo]:
    """Parse git history and return enriched commit information.

    Uses a single ``git log --numstat`` subprocess instead of per-commit
    stat calls via GitPython, which is orders of magnitude faster on
    large repositories.
    """
    since_date = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=since_days)
    since_date.isoformat()

    # Use a unique record separator that won't appear in commit messages.
    # Format each commit as: RS hash RS author RS email RS timestamp RS message RS
    # followed by numstat lines until the next RS.
    rs = "\x1e"  # ASCII Record Separator
    fmt = f"{rs}%H{rs}%aN{rs}%aE{rs}%aI{rs}%B{rs}"

    try:
        result = subprocess.run(
            [
                "git",
                "log",
                f"--since={since_date.isoformat()}",
                f"--format={fmt}",
                "--numstat",
            ],
            capture_output=True,
            text=True,
            cwd=str(repo_path),
            timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0:
        return []

    raw = result.stdout
    if not raw.strip():
        return []

    commits: list[CommitInfo] = []

    # Split on the record separator.
    # Format per commit: RS hash RS author RS email RS ts RS message RS
    # Numstat lines follow AFTER the trailing RS, until the next commit's
    # leading RS.  So after splitting we get groups of 6 parts:
    #   [hash, author, email, ts, message, numstat_block]
    parts = raw.split(rs)

    i = 1  # skip leading empty part
    while i + 5 < len(parts):
        full_hash = parts[i].strip()
        author = parts[i + 1].strip()
        email = parts[i + 2].strip()
        timestamp_str = parts[i + 3].strip()
        message_raw = parts[i + 4]
        numstat_block = parts[i + 5]
        i += 6

        if not full_hash or len(full_hash) < 10:
            continue

        # numstat_block contains the numstat lines between this commit's
        # trailing RS and the next commit's leading RS.
        lines = numstat_block.split("\n")

        files_changed: list[str] = []
        total_ins = 0
        total_del = 0

        for line in lines:
            if "\t" in line:
                numstat_parts = line.split("\t", 2)
                if len(numstat_parts) == 3:
                    try:
                        ins = int(numstat_parts[0]) if numstat_parts[0] != "-" else 0
                        dels = int(numstat_parts[1]) if numstat_parts[1] != "-" else 0
                        fpath = numstat_parts[2].strip()
                        if fpath:
                            files_changed.append(fpath)
                            total_ins += ins
                            total_del += dels
                            continue
                    except ValueError:
                        pass

        message = message_raw.strip()

        if file_filter and not any(f in file_filter for f in files_changed):
            continue

        # Parse timestamp
        try:
            ts = datetime.datetime.fromisoformat(timestamp_str)
        except ValueError:
            continue

        coauthors_raw = CO_AUTHOR_RE.findall(message)
        coauthors = [name for name, _email in coauthors_raw]
        is_ai, ai_conf = _detect_ai_attribution(message, coauthors)

        commits.append(
            CommitInfo(
                hash=full_hash[:12],
                author=author or "unknown",
                email=email,
                timestamp=ts,
                message=message,
                files_changed=files_changed,
                insertions=total_ins,
                deletions=total_del,
                is_ai_attributed=is_ai,
                ai_confidence=ai_conf,
                coauthors=coauthors,
            )
        )

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

    now = datetime.datetime.now(tz=datetime.UTC)
    thirty_days_ago = now - datetime.timedelta(days=30)

    histories: dict[str, FileHistory] = {}

    for fpath, fcommits in file_commits.items():
        authors = {c.author for c in fcommits}
        ai_commits = [c for c in fcommits if c.is_ai_attributed]
        recent = [c for c in fcommits if c.timestamp.astimezone(datetime.UTC) > thirty_days_ago]
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

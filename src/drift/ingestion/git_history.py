"""Git history analysis and AI-code attribution heuristics."""

from __future__ import annotations

import datetime
import json
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
    # Newer AI coding tools (2025+)
    "windsurf",
    "devin",
    "aider",
    "cline",
    "sourcegraph",
    "amazon-q",
    "gemini",
    "claude",
    "copilot-workspace",
]

# Commit messages dominated by AI tools tend to be formulaic.
# We use multiple tiers of patterns with different confidence levels.
# Tier 1 (higher confidence): very specific AI-tool patterns
# Tier 2 (lower confidence): generic "Verb + noun + noun" only when
#   combined with other weak signals (no body, exact format).

# Known AI tool email patterns in Co-authored-by tags.
# Matched against the email portion of the co-author header.
_AI_COAUTHOR_EMAILS = [
    "copilot@users.noreply.github.com",
    "noreply@cursor.sh",
    "noreply@codeium.com",
]

# High-confidence patterns: clearly auto-generated messages
_AI_MSG_TIER1 = [
    # Cursor / Copilot default messages
    re.compile(r"^(Implement|Refactor|Create) \w+ \w+ \w+", re.IGNORECASE),
    # "Add X functionality for Y" — 4+ word noun-phrase after verb
    re.compile(
        r"^(Add|Implement|Create) \w+ \w+ "
        r"(functionality|feature|support|handling|endpoint|module)\b",
        re.IGNORECASE,
    ),
    # aider-specific prefix
    re.compile(r"^aider: ", re.IGNORECASE),
]

# Low-confidence patterns: common in AI but also in humans
_AI_MSG_TIER2 = [
    re.compile(r"^(Add|Update|Fix|Remove) \w+ \w+", re.IGNORECASE),
]

DEFECT_MARKERS = re.compile(
    r"\b(fix|bug|hotfix|revert|patch|regression|broken|crash|error)\b", re.IGNORECASE,
)

# Conventional-commit format used by many AI-assisted projects.
_CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(feat|fix|chore|refactor|test|docs|style|build|ci|perf|revert)"
    r"(\(.+?\))?: .+",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# AI Tool File Indicators
# ---------------------------------------------------------------------------

# Mapping: file/dir path (relative to repo root) → tool name.
# Directories are suffixed with "/".
_AI_TOOL_FILE_INDICATORS: dict[str, str] = {
    ".claude/": "claude",
    "CLAUDE.md": "claude",
    "AGENTS.md": "agents",
    ".claudeignore": "claude",
    ".copilotignore": "copilot",
    ".github/copilot-instructions.md": "copilot",
    ".cursor/": "cursor",
    ".cursorignore": "cursor",
    ".cursorrules": "cursor",
    ".aider/": "aider",
    ".aider.conf.yml": "aider",
    ".cline/": "cline",
    "cline_docs/": "cline",
    ".windsurf/": "windsurf",
    ".codeium/": "codeium",
    ".amazon-q/": "amazon-q",
    ".continue/": "continue",
}


def detect_ai_tool_indicators(repo_path: Path) -> list[str]:
    """Scan the repository root for known AI tool configuration files.

    Returns a sorted deduplicated list of detected tool names
    (e.g. ``["claude", "copilot"]``).
    """
    detected: set[str] = set()
    for indicator, tool in _AI_TOOL_FILE_INDICATORS.items():
        target = repo_path / indicator.rstrip("/")
        if target.exists():
            detected.add(tool)
    return sorted(detected)


def indicator_boost_for_tools(tools: list[str]) -> float:
    """Map the number of detected AI tools to a confidence boost value.

    - 0 tools → 0.0  (no boost)
    - 1 tool  → 0.10
    - 2 tools → 0.15
    - 3+ tools → 0.20
    """
    n = len(tools)
    if n == 0:
        return 0.0
    if n == 1:
        return 0.10
    if n == 2:
        return 0.15
    return 0.20


def _detect_ai_attribution(
    message: str,
    coauthors: list[str],
    *,
    indicator_boost: float = 0.0,
) -> tuple[bool, float]:
    """Determine if a commit is likely AI-attributed.

    Returns (is_ai, confidence) where confidence is 0.0-1.0.

    Uses tiered heuristics:
    - Co-author tag from known AI tool → 0.95 confidence
    - Tier 1 formulaic message (specific AI patterns) → 0.40 + boost
    - Conventional commit in AI-tool repo → 0.20 + boost
    - Tier 2 formulaic message (generic verb-noun) → 0.15 + boost

    ``indicator_boost`` is added to the base confidence of message-based
    tiers (capped at 0.95).  It is derived from the number of AI tool
    configuration files found in the repository
    (see :func:`indicator_boost_for_tools`).
    """
    # Strong signal: co-author tag from known AI tool (name match)
    for coauthor in coauthors:
        lower = coauthor.lower()
        for marker in AI_COAUTHOR_MARKERS:
            if marker in lower:
                return True, 0.95
        # Strong signal: co-author email from known AI tool
        for email_marker in _AI_COAUTHOR_EMAILS:
            if email_marker in lower:
                return True, 0.95

    msg_first_line = message.split("\n", maxsplit=1)[0].strip()
    msg_body = message.split("\n", 1)[1].strip() if "\n" in message else ""

    # Tier 1: specific AI patterns — higher confidence
    tier1_match = any(p.match(msg_first_line) for p in _AI_MSG_TIER1)
    if tier1_match and len(msg_first_line) < 72 and not msg_body:
        conf = min(0.40 + indicator_boost, 0.95)
        return True, round(conf, 2)

    # Tier 1.5: conventional-commit format — meaningful only with tool indicators
    if indicator_boost > 0:
        conv_match = _CONVENTIONAL_COMMIT_RE.match(msg_first_line)
        if conv_match and not msg_body:
            conf = min(0.40 + indicator_boost, 0.95)
            return True, round(conf, 2)

    # Tier 2: generic verb-noun patterns — only weak signal
    tier2_match = any(p.match(msg_first_line) for p in _AI_MSG_TIER2)
    if tier2_match and len(msg_first_line) < 50 and not msg_body:
        conf = min(0.15 + indicator_boost, 0.95)
        return False, round(conf, 2)

    return False, 0.0


def _is_defect_correlated(message: str) -> bool:
    return bool(DEFECT_MARKERS.search(message))


def _git_repo_prefix(repo_path: Path) -> str:
    """Return the POSIX prefix of *repo_path* relative to the git root.

    When ``repo_path`` **is** the git root the prefix is ``""``.
    When it is a subdirectory (e.g. ``/repo/sub/dir``) the prefix is
    ``"sub/dir/"`` so that git-root-relative paths can be mapped to
    repo-relative paths by stripping the prefix.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(repo_path),
            timeout=10,
            stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            return ""
        git_root = Path(result.stdout.strip()).resolve()
        resolved = repo_path.resolve()
        if resolved == git_root:
            return ""
        try:
            rel = resolved.relative_to(git_root).as_posix()
            return rel + "/"
        except ValueError:
            return ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


# ---------------------------------------------------------------------------
# Git History Parser
# ---------------------------------------------------------------------------


@dataclass
class _BulkCommitData:
    """Aggregated per-commit data from bulk git log."""

    files: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0


def _run_git_log_cmd(
    repo_path: Path,
    since_date: datetime.datetime,
    fmt: str,
    rev_range: str | None,
) -> str | None:
    """Run git log and return stdout, or None on error."""
    try:
        cmd = [
            "git",
            "log",
            f"--since={since_date.isoformat()}",
            f"--format={fmt}",
            "--numstat",
        ]
        if rev_range:
            cmd.append(rev_range)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(repo_path),
            timeout=60,
            stdin=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    raw = result.stdout
    return raw if raw.strip() else None


def _parse_numstat_block(
    numstat_block: str,
    repo_prefix: str,
) -> tuple[list[str], int, int]:
    """Parse a numstat block into (files_changed, total_ins, total_del)."""
    files_changed: list[str] = []
    total_ins = 0
    total_del = 0
    for line in numstat_block.split("\n"):
        if "\t" not in line:
            continue
        numstat_parts = line.split("\t", 2)
        if len(numstat_parts) != 3:
            continue
        try:
            ins = int(numstat_parts[0]) if numstat_parts[0] != "-" else 0
            dels = int(numstat_parts[1]) if numstat_parts[1] != "-" else 0
            fpath = numstat_parts[2].strip()
            if not fpath:
                continue
            if repo_prefix and fpath.startswith(repo_prefix):
                fpath = fpath[len(repo_prefix):]
            elif repo_prefix:
                continue
            files_changed.append(fpath)
            total_ins += ins
            total_del += dels
        except ValueError:
            pass
    return files_changed, total_ins, total_del


def _parse_commit_record(
    parts: list[str],
    i: int,
    repo_prefix: str,
    ai_confidence_threshold: float,
    indicator_boost: float,
    file_filter: set[str] | None,
) -> CommitInfo | None:
    """Parse one commit record from split log parts, returning CommitInfo or None."""
    full_hash = parts[i].strip()
    author = parts[i + 1].strip()
    email = parts[i + 2].strip()
    timestamp_str = parts[i + 3].strip()
    message_raw = parts[i + 4]
    numstat_block = parts[i + 5]

    if not full_hash or len(full_hash) < 10:
        return None

    files_changed, total_ins, total_del = _parse_numstat_block(numstat_block, repo_prefix)
    message = message_raw.strip()

    if file_filter and not any(f in file_filter for f in files_changed):
        return None

    try:
        ts = datetime.datetime.fromisoformat(timestamp_str)
    except ValueError:
        return None

    coauthors_raw = CO_AUTHOR_RE.findall(message)
    coauthors = [name for name, _email in coauthors_raw]
    _is_ai_raw, ai_conf = _detect_ai_attribution(
        message, coauthors, indicator_boost=indicator_boost,
    )
    is_ai = ai_conf >= ai_confidence_threshold

    return CommitInfo(
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


def parse_git_history(
    repo_path: Path,
    since_days: int = 90,
    file_filter: set[str] | None = None,
    *,
    ai_confidence_threshold: float = 0.50,
    indicator_boost: float = 0.0,
    rev_range: str | None = None,
) -> list[CommitInfo]:
    """Parse git history and return enriched commit information.

    Uses a single ``git log --numstat`` subprocess instead of per-commit
    stat calls via GitPython, which is orders of magnitude faster on
    large repositories.
    """
    since_date = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=since_days)

    # When repo_path is a subdirectory of the git root, git log returns
    # paths relative to the root.  Compute the prefix so we can map those
    # paths back to repo-relative paths that match file_filter (#117).
    repo_prefix = _git_repo_prefix(repo_path)

    # Use a unique record separator that won't appear in commit messages.
    # Format each commit as: RS hash RS author RS email RS timestamp RS message RS
    # followed by numstat lines until the next RS.
    rs = "\x1e"  # ASCII Record Separator
    fmt = f"{rs}%H{rs}%aN{rs}%aE{rs}%aI{rs}%B{rs}"

    raw = _run_git_log_cmd(repo_path, since_date, fmt, rev_range)
    if raw is None:
        return []

    commits: list[CommitInfo] = []
    parts = raw.split(rs)

    i = 1  # skip leading empty part
    while i + 5 < len(parts):
        commit = _parse_commit_record(
            parts, i, repo_prefix, ai_confidence_threshold, indicator_boost, file_filter
        )
        if commit is not None:
            commits.append(commit)
        i += 6

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


_HISTORY_INDEX_SCHEMA_VERSION = 1


def _history_index_paths(cache_root: Path, subdir: str = "git_history") -> tuple[Path, Path, Path]:
    base = cache_root / subdir
    return base, base / "manifest.json", base / "commits.jsonl"


def _git_head_sha(repo_path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            stdin=subprocess.DEVNULL,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    head = result.stdout.strip()
    return head or None


def _is_ancestor(repo_path: Path, older: str, newer: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "merge-base", "--is-ancestor", older, newer],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            stdin=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _serialize_commit(commit: CommitInfo) -> dict[str, object]:
    return {
        "hash": commit.hash,
        "author": commit.author,
        "email": commit.email,
        "timestamp": commit.timestamp.isoformat(),
        "message": commit.message,
        "files_changed": commit.files_changed,
        "insertions": commit.insertions,
        "deletions": commit.deletions,
        "is_ai_attributed": commit.is_ai_attributed,
        "ai_confidence": commit.ai_confidence,
        "coauthors": commit.coauthors,
    }


def _deserialize_commit(payload: dict[str, object]) -> CommitInfo | None:
    try:
        ts_raw = payload.get("timestamp")
        if not isinstance(ts_raw, str):
            return None
        ts = datetime.datetime.fromisoformat(ts_raw)
        files_changed_raw = payload.get("files_changed", [])
        files_changed = (
            [str(x) for x in files_changed_raw] if isinstance(files_changed_raw, list) else []
        )
        coauthors_raw = payload.get("coauthors", [])
        coauthors = [str(x) for x in coauthors_raw] if isinstance(coauthors_raw, list) else []

        insertions_raw = payload.get("insertions", 0)
        deletions_raw = payload.get("deletions", 0)
        ai_confidence_raw = payload.get("ai_confidence", 0.0)
        insertions = (
            int(insertions_raw)
            if isinstance(insertions_raw, (int, float, str))
            else 0
        )
        deletions = (
            int(deletions_raw)
            if isinstance(deletions_raw, (int, float, str))
            else 0
        )
        ai_confidence = (
            float(ai_confidence_raw)
            if isinstance(ai_confidence_raw, (int, float, str))
            else 0.0
        )
        return CommitInfo(
            hash=str(payload.get("hash", "")),
            author=str(payload.get("author", "unknown")),
            email=str(payload.get("email", "")),
            timestamp=ts,
            message=str(payload.get("message", "")),
            files_changed=files_changed,
            insertions=insertions,
            deletions=deletions,
            is_ai_attributed=bool(payload.get("is_ai_attributed", False)),
            ai_confidence=ai_confidence,
            coauthors=coauthors,
        )
    except (TypeError, ValueError):
        return None


def _read_manifest(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")


def _read_commits_jsonl(path: Path) -> list[CommitInfo]:
    if not path.exists():
        return []

    commits: list[CommitInfo] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                commit = _deserialize_commit(payload)
                if commit is not None:
                    commits.append(commit)
    except OSError:
        return []
    return commits


def _append_commits_jsonl(path: Path, commits: list[CommitInfo]) -> None:
    if not commits:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for commit in commits:
            fh.write(json.dumps(_serialize_commit(commit), ensure_ascii=True, sort_keys=True))
            fh.write("\n")


def _rewrite_commits_jsonl(path: Path, commits: list[CommitInfo]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for commit in commits:
            fh.write(json.dumps(_serialize_commit(commit), ensure_ascii=True, sort_keys=True))
            fh.write("\n")


def _prune_to_since_window(commits: list[CommitInfo], since_days: int) -> list[CommitInfo]:
    since_date = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=since_days)
    filtered = [c for c in commits if c.timestamp.astimezone(datetime.UTC) >= since_date]
    return sorted(filtered, key=lambda c: c.timestamp, reverse=True)


def _dedupe_commits(commits: list[CommitInfo]) -> list[CommitInfo]:
    by_hash: dict[str, CommitInfo] = {}
    for commit in commits:
        by_hash.setdefault(commit.hash, commit)
    return sorted(by_hash.values(), key=lambda c: c.timestamp, reverse=True)


def load_or_update_git_history_index(
    repo_path: Path,
    *,
    cache_root: Path,
    since_days: int,
    ai_confidence_threshold: float = 0.50,
    indicator_boost: float = 0.0,
    index_subdir: str = "git_history",
) -> list[CommitInfo]:
    """Load or incrementally update persistent git-history index.

    The commit store is append-only for fast-path updates (HEAD is descendant
    of indexed HEAD). Any non-linear history transition triggers a full rebuild.
    """
    current_head = _git_head_sha(repo_path)
    if current_head is None:
        return []

    index_dir, manifest_path, commits_path = _history_index_paths(cache_root, index_subdir)
    manifest = _read_manifest(manifest_path)

    params = {
        "since_days": since_days,
        "ai_confidence_threshold": round(ai_confidence_threshold, 6),
        "indicator_boost": round(indicator_boost, 6),
    }
    repo_key = repo_path.resolve().as_posix()

    if (
        manifest is None
        or manifest.get("schema_version") != _HISTORY_INDEX_SCHEMA_VERSION
        or manifest.get("repo_key") != repo_key
        or manifest.get("params") != params
    ):
        commits = parse_git_history(
            repo_path,
            since_days=since_days,
            file_filter=None,
            ai_confidence_threshold=ai_confidence_threshold,
            indicator_boost=indicator_boost,
        )
        commits = _dedupe_commits(commits)
        _rewrite_commits_jsonl(commits_path, commits)
        _write_manifest(
            manifest_path,
            {
                "schema_version": _HISTORY_INDEX_SCHEMA_VERSION,
                "repo_key": repo_key,
                "head": current_head,
                "params": params,
                "updated_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
            },
        )
        return _prune_to_since_window(commits, since_days)

    indexed_head = manifest.get("head")
    if not isinstance(indexed_head, str) or not indexed_head:
        commits = parse_git_history(
            repo_path,
            since_days=since_days,
            file_filter=None,
            ai_confidence_threshold=ai_confidence_threshold,
            indicator_boost=indicator_boost,
        )
        commits = _dedupe_commits(commits)
        _rewrite_commits_jsonl(commits_path, commits)
        _write_manifest(
            manifest_path,
            {
                "schema_version": _HISTORY_INDEX_SCHEMA_VERSION,
                "repo_key": repo_key,
                "head": current_head,
                "params": params,
                "updated_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
            },
        )
        return _prune_to_since_window(commits, since_days)

    existing_commits = _read_commits_jsonl(commits_path)

    if indexed_head == current_head:
        return _prune_to_since_window(_dedupe_commits(existing_commits), since_days)

    if _is_ancestor(repo_path, indexed_head, current_head):
        delta = parse_git_history(
            repo_path,
            since_days=since_days,
            file_filter=None,
            ai_confidence_threshold=ai_confidence_threshold,
            indicator_boost=indicator_boost,
            rev_range=f"{indexed_head}..{current_head}",
        )
        if delta:
            _append_commits_jsonl(commits_path, _dedupe_commits(delta))
            merged = _dedupe_commits(existing_commits + delta)
        else:
            merged = _dedupe_commits(existing_commits)
        _write_manifest(
            manifest_path,
            {
                "schema_version": _HISTORY_INDEX_SCHEMA_VERSION,
                "repo_key": repo_key,
                "head": current_head,
                "params": params,
                "updated_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
            },
        )
        return _prune_to_since_window(merged, since_days)

    # History was rewritten (e.g., force-push/rebase) — rebuild index safely.
    commits = parse_git_history(
        repo_path,
        since_days=since_days,
        file_filter=None,
        ai_confidence_threshold=ai_confidence_threshold,
        indicator_boost=indicator_boost,
    )
    commits = _dedupe_commits(commits)
    _rewrite_commits_jsonl(commits_path, commits)
    _write_manifest(
        manifest_path,
        {
            "schema_version": _HISTORY_INDEX_SCHEMA_VERSION,
            "repo_key": repo_key,
            "head": current_head,
            "params": params,
            "updated_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        },
    )
    return _prune_to_since_window(commits, since_days)


# ---------------------------------------------------------------------------
# Co-Change Coupling
# ---------------------------------------------------------------------------


@dataclass
class CoChangePair:
    """Two files that are frequently changed together."""

    file_a: str
    file_b: str
    co_change_count: int
    total_commits_a: int
    total_commits_b: int
    confidence: float  # co_change_count / min(total_a, total_b)


def build_co_change_pairs(
    commits: list[CommitInfo],
    known_files: set[str] | None = None,
    *,
    min_co_changes: int = 3,
    min_confidence: float = 0.3,
) -> list[CoChangePair]:
    """Identify file pairs frequently changed together.

    Only considers internal files (in *known_files* if given).
    Returns pairs sorted by confidence descending.

    Complexity: O(C × F²) where C = commits, F = avg files per commit.
    Bounded by filtering commits with >20 files (bulk refactors).

    Each commit is weighted inversely by the number of files it touches,
    so that bulk/sweep commits contribute less per pair than surgical
    two-file commits.  The hard cut at >20 files is kept as a secondary
    guard.
    """
    from itertools import combinations

    pair_counts: dict[tuple[str, str], float] = defaultdict(float)
    file_commit_counts: dict[str, float] = defaultdict(float)

    for commit in commits:
        files = commit.files_changed
        if known_files:
            files = [f for f in files if f in known_files]
        # Skip bulk commits (refactors, renames) that would create
        # spurious co-change signals.
        if len(files) > 20 or len(files) < 2:
            continue

        # Weight inversely by number of files: surgical commits (2 files)
        # count fully (1.0); a 15-file commit counts ~0.07 per pair.
        weight = 1.0 / max(1, len(files) - 1)

        for f in files:
            file_commit_counts[f] += weight

        for a, b in combinations(sorted(files), 2):
            pair_counts[(a, b)] += weight

    pairs: list[CoChangePair] = []
    for (a, b), count in pair_counts.items():
        if count < min_co_changes:
            continue
        total_a = file_commit_counts[a]
        total_b = file_commit_counts[b]
        confidence = count / min(total_a, total_b)
        if confidence < min_confidence:
            continue
        pairs.append(
            CoChangePair(
                file_a=a,
                file_b=b,
                co_change_count=round(count),
                total_commits_a=round(total_a),
                total_commits_b=round(total_b),
                confidence=round(confidence, 3),
            ),
        )

    pairs.sort(key=lambda p: p.confidence, reverse=True)
    return pairs

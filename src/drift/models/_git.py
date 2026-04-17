"""Git-related data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import datetime
    from pathlib import Path


@dataclass
class CommitInfo:
    hash: str
    author: str
    email: str
    timestamp: datetime.datetime
    message: str
    files_changed: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0
    is_ai_attributed: bool = False
    ai_confidence: float = 0.0
    coauthors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not (0.0 <= self.ai_confidence <= 1.0):
            raise ValueError(
                f"CommitInfo.ai_confidence must be in [0, 1], got {self.ai_confidence}"
            )


@dataclass
class FileHistory:
    """Git history statistics for a single file."""

    path: Path
    total_commits: int = 0
    unique_authors: int = 0
    ai_attributed_commits: int = 0
    change_frequency_30d: float = 0.0
    defect_correlated_commits: int = 0
    last_modified: datetime.datetime | None = None
    first_seen: datetime.datetime | None = None


# ---------------------------------------------------------------------------
# Attribution Models (ADR-034)
# ---------------------------------------------------------------------------


@dataclass
class BlameLine:
    """A single line result from git blame --porcelain."""

    line_no: int
    commit_hash: str
    author: str
    email: str
    date: datetime.date
    content: str = ""


@dataclass
class Attribution:
    """Causal provenance for a finding — who introduced the drifting code.

    Populated by the attribution enrichment pipeline when
    ``attribution.enabled`` is set in drift.yaml.
    """

    commit_hash: str
    author: str
    email: str
    date: datetime.date
    branch_hint: str | None = None
    ai_attributed: bool = False
    ai_confidence: float = 0.0
    commit_message: str = ""

    def __post_init__(self) -> None:
        if not (0.0 <= self.ai_confidence <= 1.0):
            raise ValueError(
                f"Attribution.ai_confidence must be in [0, 1], got {self.ai_confidence}"
            )

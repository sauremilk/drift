"""PatchWriter base interface and PatchResult model (ADR-076)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum, auto
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from drift.models import Finding


class PatchResultStatus(StrEnum):
    """Outcome of a single PatchWriter.generate_patch() call."""

    GENERATED = auto()       # Patch produced; file not written yet
    APPLIED = auto()         # Patch written to file successfully
    SKIPPED = auto()         # Nothing to patch (e.g. docstring already present)
    UNSUPPORTED = auto()     # Signal/language not handled by this writer
    FAILED = auto()          # Internal error during patch generation
    ROLLED_BACK = auto()     # Applied patch reverted after patch_check rejection


@dataclass
class PatchResult:
    """Result of a single patch operation."""

    status: PatchResultStatus
    edit_kind: str
    file_path: Path | None = None
    #: Unified diff string (empty for SKIPPED / UNSUPPORTED / FAILED)
    diff: str = ""
    #: New source content after patching (used for rollback)
    patched_source: str | None = None
    #: Original source before patching (used for rollback)
    original_source: str | None = None
    reason: str = ""
    metadata: dict = field(default_factory=dict)


class PatchWriter(ABC):
    """Abstract base class for all source-code patch writers."""

    @property
    @abstractmethod
    def edit_kind(self) -> str:
        """The edit_kind constant this writer handles."""

    @abstractmethod
    def can_write(self, finding: Finding) -> bool:
        """Return True if this writer can generate a patch for *finding*.

        Implementations must return False for:
        - unsupported languages (v1: Python-only)
        - findings where a patch would be a no-op
        - findings with insufficient metadata
        """

    @abstractmethod
    def generate_patch(self, finding: Finding, source: str) -> PatchResult:
        """Generate a patch for *finding* applied to *source*.

        Returns a :class:`PatchResult` with status GENERATED on success,
        SKIPPED when the patch is a no-op, or FAILED on error.
        Does NOT write to disk — the caller decides whether to apply.
        """

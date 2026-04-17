"""Patch-engine models: PatchIntent, PatchVerdict and helpers (ADR-074)."""

from __future__ import annotations

import datetime as _dt
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PatchStatus(StrEnum):
    """Verdict status for a patch transaction."""

    CLEAN = "clean"
    REVIEW_REQUIRED = "review_required"
    ROLLBACK_RECOMMENDED = "rollback_recommended"


class BlastRadius(StrEnum):
    """Declared scope of a patch change."""

    LOCAL = "local"
    MODULE = "module"
    REPO = "repo"


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


class DiffMetrics(BaseModel):
    """Quantitative summary of a patch diff."""

    lines_added: int
    lines_removed: int
    files_changed: int
    files_outside_scope: list[str] = Field(default_factory=list)


class AcceptanceResult(BaseModel):
    """Evaluation of a single acceptance criterion."""

    criterion: str
    met: bool | None = None  # None = not measurable
    evidence: str = ""


# ---------------------------------------------------------------------------
# PatchIntent — declared before editing
# ---------------------------------------------------------------------------


class PatchIntent(BaseModel):
    """Agent-declared intent for a patch transaction (ADR-074).

    Created via ``patch_begin`` before editing begins.  Captures which files
    will be touched, what the expected outcome is, and what constraints apply.
    """

    task_id: str
    session_id: str | None = None
    declared_files: list[str]
    forbidden_paths: list[str] = Field(default_factory=list)
    expected_outcome: str
    blast_radius: BlastRadius = BlastRadius.LOCAL
    max_diff_lines: int | None = None
    quality_constraints: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    created_at: _dt.datetime = Field(default_factory=lambda: _dt.datetime.now(_dt.UTC))

    def to_api_dict(self) -> dict[str, Any]:
        """Serialize for API / MCP responses."""
        return self.model_dump(mode="json")


# ---------------------------------------------------------------------------
# PatchVerdict — computed after editing
# ---------------------------------------------------------------------------


class PatchVerdict(BaseModel):
    """Machine-readable verdict for a completed patch transaction (ADR-074).

    Computed by ``patch_check`` after the agent has finished editing.
    """

    task_id: str
    status: PatchStatus
    scope_compliance: bool
    scope_violations: list[str] = Field(default_factory=list)
    diff_metrics: DiffMetrics
    architecture_impact: list[dict[str, Any]] = Field(default_factory=list)
    test_passed: bool | None = None
    acceptance_met: list[AcceptanceResult] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    merge_readiness: str = "ready"
    checked_at: _dt.datetime = Field(default_factory=lambda: _dt.datetime.now(_dt.UTC))

    def to_api_dict(self) -> dict[str, Any]:
        """Serialize for API / MCP responses."""
        return self.model_dump(mode="json")

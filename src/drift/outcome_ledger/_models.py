"""Immutable Pydantic-Modelle fuer den Outcome-Feedback-Ledger (ADR-088)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

LEDGER_SCHEMA_VERSION: int = 1
STALENESS_WARNING_DAYS: int = 90
STALENESS_HISTORICAL_DAYS: int = 180


class TrajectoryDirection(StrEnum):
    IMPROVED = "improved"
    REGRESSED = "regressed"
    NEUTRAL = "neutral"
    INDETERMINATE = "indeterminate"


class AuthorType(StrEnum):
    HUMAN = "human"
    AI = "ai"
    MIXED = "mixed"


class RecommendationOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_fingerprint: str = Field(min_length=1)
    signal_type: str = Field(min_length=1)
    task_kind: str | None = None
    expected_delta: float | None = None
    observed_delta: float
    resolved: bool
    correlation_confidence: float = Field(ge=0.0, le=1.0)
    file_paths: tuple[str, ...] = Field(default_factory=tuple)


class MergeTrajectory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=LEDGER_SCHEMA_VERSION, ge=1)
    merge_commit: str = Field(min_length=7)
    parent_commit: str = Field(min_length=7)
    timestamp: str
    author_type: AuthorType
    ai_attribution_confidence: float = Field(ge=0.0, le=1.0)
    pre_score: float
    post_score: float
    delta: float
    direction: TrajectoryDirection
    per_signal_delta: dict[str, float] = Field(default_factory=dict)
    recommendation_outcomes: tuple[RecommendationOutcome, ...] = Field(default_factory=tuple)
    staleness_days: int = Field(default=0, ge=0)
    notes: tuple[str, ...] = Field(default_factory=tuple)

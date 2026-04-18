"""Data models for the Skill Synthesizer."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Literal

from drift.calibration.history import FindingSnapshot


@dataclass(slots=True)
class ClusterFeedback:
    """Aggregated TP/FP/FN counts for a finding cluster."""

    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.fn

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom > 0 else 1.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom > 0 else 1.0

    def to_dict(self) -> dict[str, Any]:
        return {"tp": self.tp, "fp": self.fp, "fn": self.fn}


def _compute_cluster_id(signal_type: str, module_path: str, rule_id: str | None) -> str:
    """Compute a deterministic cluster ID from the stable key."""
    raw = f"{signal_type}:{module_path}:{rule_id or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(slots=True)
class FindingCluster:
    """A group of recurring findings sharing signal type and module path.

    The stable key ``(signal_type, module_path, rule_id)`` is
    line-number-independent so clusters survive refactorings.
    """

    cluster_id: str
    signal_type: str
    rule_id: str | None
    module_path: str
    affected_files: list[str]
    occurrence_count: int
    recurrence_rate: float  # fraction of scans where cluster appeared
    first_seen: str  # ISO timestamp
    last_seen: str  # ISO timestamp
    trend: Literal["improving", "stable", "degrading"]
    feedback: ClusterFeedback
    representative_findings: list[FindingSnapshot] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "signal_type": self.signal_type,
            "rule_id": self.rule_id,
            "module_path": self.module_path,
            "affected_files": list(self.affected_files),
            "occurrence_count": self.occurrence_count,
            "recurrence_rate": round(self.recurrence_rate, 3),
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "trend": self.trend,
            "feedback": self.feedback.to_dict(),
            "representative_findings": [
                {"signal_type": f.signal_type, "file_path": f.file_path, "score": f.score}
                for f in self.representative_findings
            ],
        }


@dataclass(slots=True)
class SkillDraft:
    """A synthesized skill draft — either guard (preventive) or repair (fix).

    Generated from a ``FindingCluster`` enriched with ``ArchGraph`` metadata.
    """

    kind: Literal["guard", "repair"]
    name: str  # kebab-case
    module_path: str
    trigger: str  # when the skill should activate
    goal: str  # what the skill achieves
    trigger_signals: list[str]  # signal abbreviations
    constraints: list[str]  # from ADR/decisions
    negative_examples: list[str]  # from FP feedback — "don't apply when..."
    fix_patterns: list[str]  # aggregated fix hints (repair only)
    verify_commands: list[str]
    source_cluster: FindingCluster
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "module_path": self.module_path,
            "trigger": self.trigger,
            "goal": self.goal,
            "trigger_signals": list(self.trigger_signals),
            "constraints": list(self.constraints),
            "negative_examples": list(self.negative_examples),
            "fix_patterns": list(self.fix_patterns),
            "verify_commands": list(self.verify_commands),
            "source_cluster": self.source_cluster.to_dict(),
            "confidence": round(self.confidence, 3),
        }


@dataclass(slots=True)
class TriageDecision:
    """Triage result for a skill draft: new, merge into existing, or discard."""

    draft: SkillDraft
    action: Literal["new", "merge", "discard"]
    merge_target: str | None  # existing skill name, if action == "merge"
    reason: str
    sprawl_risk: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "draft": self.draft.to_dict(),
            "action": self.action,
            "merge_target": self.merge_target,
            "reason": self.reason,
            "sprawl_risk": self.sprawl_risk,
        }


@dataclass(slots=True)
class SkillEffectivenessRecord:
    """Tracks whether a synthesized skill reduced finding recurrence."""

    skill_name: str
    created_at: str  # ISO timestamp
    cluster_id: str
    pre_recurrence_rate: float
    post_recurrence_rate: float | None  # None until enough scans collected
    scans_since_creation: int

    @property
    def effectiveness(self) -> float | None:
        """Return effectiveness ratio, or None if insufficient data."""
        if self.post_recurrence_rate is None or self.scans_since_creation < 3:
            return None
        if self.pre_recurrence_rate == 0:
            return 0.0
        return round(1.0 - (self.post_recurrence_rate / self.pre_recurrence_rate), 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "created_at": self.created_at,
            "cluster_id": self.cluster_id,
            "pre_recurrence_rate": round(self.pre_recurrence_rate, 3),
            "post_recurrence_rate": (
                round(self.post_recurrence_rate, 3)
                if self.post_recurrence_rate is not None
                else None
            ),
            "scans_since_creation": self.scans_since_creation,
            "effectiveness": self.effectiveness,
        }

"""Agent task model (agent-tasks output format)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from drift.models._patch import PatchIntent

from drift.models._context import NegativeContext
from drift.models._enums import (
    AutomationFit,
    ChangeScope,
    RegressionPattern,
    RepairMaturity,
    ReviewRisk,
    Severity,
    TaskComplexity,
    VerificationStrength,
)

# ---------------------------------------------------------------------------
# Consolidation Group (ADR-073)
# ---------------------------------------------------------------------------


@dataclass
class ConsolidationGroup:
    """A cluster of batch-eligible tasks that can be resolved by one consolidation.

    Produced by :func:`drift.task_graph.build_consolidation_groups` and
    included in fix-plan responses as ``consolidation_opportunities``.
    """

    group_id: str
    signal: str
    edit_kind: str
    instance_count: int
    canonical_file: str | None = None
    affected_files: list[str] = field(default_factory=list)
    task_ids: list[str] = field(default_factory=list)
    estimated_net_finding_reduction: int = 0

    def to_api_dict(self) -> dict[str, Any]:
        """Serialize for API responses."""
        return {
            "group_id": self.group_id,
            "signal": self.signal,
            "edit_kind": self.edit_kind,
            "instance_count": self.instance_count,
            "canonical_file": self.canonical_file,
            "affected_files": self.affected_files[:15],
            "affected_files_total": len(self.affected_files),
            "task_ids": self.task_ids,
            "estimated_net_finding_reduction": self.estimated_net_finding_reduction,
        }


@dataclass
class AgentTask:
    """An atomic, machine-readable repair task derived from a Finding."""

    id: str
    signal_type: str  # SignalType value for core signals, arbitrary str for plugins
    severity: Severity
    priority: int
    title: str
    description: str
    action: str
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    symbol: str | None = None
    related_files: list[str] = field(default_factory=list)
    complexity: TaskComplexity = TaskComplexity.MEDIUM
    expected_effect: str = ""
    success_criteria: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    # Phase 1: Automation fitness classification
    automation_fit: AutomationFit = AutomationFit.MEDIUM
    review_risk: ReviewRisk = ReviewRisk.MEDIUM
    change_scope: ChangeScope = ChangeScope.LOCAL
    verification_strength: VerificationStrength = VerificationStrength.MODERATE
    # Phase 2: Do-not-over-fix guardrails
    constraints: list[str] = field(default_factory=list)
    # Phase 4: Signal-specific repair maturity
    repair_maturity: RepairMaturity = RepairMaturity.EXPERIMENTAL
    # Negative context: anti-patterns the agent must NOT reproduce
    negative_context: list[NegativeContext] = field(default_factory=list)
    # Expected score reduction when this task is resolved
    expected_score_delta: float = 0.0
    # ADR-025 Phase A: Task-graph fields for orchestration
    blocks: list[str] = field(default_factory=list)  # inverse of depends_on
    batch_group: str | None = None  # cluster ID for co-fixable tasks
    preferred_order: int = 0  # topological sort index within session
    parallel_with: list[str] = field(default_factory=list)  # task IDs safe to run concurrently
    # Signal-specific, ordered verification steps (machine-executable)
    verify_plan: list[dict[str, Any]] = field(default_factory=list)
    # ADR-064: shadow-verify for cross-file-risky edit_kinds
    shadow_verify: bool = False  # True when drift_nudge is insufficient for verification
    shadow_verify_scope: list[str] = field(default_factory=list)  # files to re-scan
    # Repair template registry fields (ADR-065)
    # None = insufficient outcome data in the registry (<3 entries)
    template_confidence: float | None = None
    regression_guidance: list[RegressionPattern] = field(default_factory=list)
    # ADR-072: Outcome-informed repair recommendations
    similar_outcomes: dict[str, Any] | None = None
    # ADR-073: Consolidation opportunity back-reference
    consolidation_group_id: str | None = None

    def to_patch_intent(self, session_id: str | None = None) -> PatchIntent:
        """Convert this task to a PatchIntent for the Patch Engine (ADR-074)."""
        from drift.models._patch import BlastRadius, PatchIntent

        scope_map = {
            ChangeScope.LOCAL: BlastRadius.LOCAL,
            ChangeScope.MODULE: BlastRadius.MODULE,
            ChangeScope.CROSS_MODULE: BlastRadius.REPO,
        }
        blast = scope_map.get(self.change_scope, BlastRadius.LOCAL)
        declared: list[str] = []
        if self.file_path:
            declared.append(self.file_path)
        declared.extend(self.related_files)
        return PatchIntent(
            task_id=self.id,
            session_id=session_id,
            declared_files=declared,
            constraints=list(self.constraints),
            blast_radius=blast,
            expected_outcome=self.title,
            acceptance_criteria=list(self.success_criteria),
        )

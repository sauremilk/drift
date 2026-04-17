"""Machine-readable task specification for agent-driven workflows.

Provides structured task descriptions that replace ambiguous natural-language
specifications with validated, constraint-bearing schemas.  Builds on the
existing ``AgentObjective`` in ``drift.config`` but adds scope boundaries,
layer affinity, quality constraints, and gate-requirement flags that enable
pre-flight validation before implementation begins.

Example YAML (embedded in drift.yaml or standalone)::

    task:
      goal: "Add phantom-reference signal for stale imports"
      affected_layers:
        - signals
      scope_boundaries:
        - "src/drift/signals/phantom_reference.py"
        - "tests/test_phantom_reference*.py"
      quality_constraints:
        - "Precision >= 70% on ground-truth fixtures"
        - "No regressions on existing signal scores"
      acceptance_criteria:
        - "Signal registered in config.py with weight > 0"
        - "FMEA entry added for FP and FN"
      requires_adr: true
      requires_audit_update: true
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ArchitectureLayer(StrEnum):
    """Valid architecture layers in the Drift data-flow pipeline."""

    SIGNALS = "signals"
    INGESTION = "ingestion"
    SCORING = "scoring"
    OUTPUT = "output"
    COMMANDS = "commands"
    CONFIG = "config"
    PLUGINS = "plugins"
    TESTS = "tests"
    SCRIPTS = "scripts"
    DOCS = "docs"
    PROMPTS = "prompts"


@dataclass(slots=True)
class TaskSpecValidationResult:
    """Structured semantic validation result for TaskSpec checks."""

    is_valid: bool
    errors: list[str]
    warnings: list[str]


class TaskSpec(BaseModel):
    """Structured, machine-readable task specification.

    Replaces ambiguous natural-language task descriptions with a validated
    schema that makes scope, constraints, and acceptance criteria explicit.
    Enables pre-flight validation of gate requirements before implementation.

    Args:
        goal: One-sentence description of the task objective.
        affected_layers: Architecture layers this task will modify.
        scope_boundaries: Glob patterns defining allowed file modifications.
        forbidden_paths: Glob patterns the task must not touch.
        quality_constraints: Measurable quality requirements.
        acceptance_criteria: Conditions that define task completion.
        requires_adr: Whether an ADR must exist before implementation.
        requires_audit_update: Whether audit artifacts must be updated.
        commit_type: Expected conventional commit type.
        depends_on: Other tasks or ADRs this task depends on.
    """

    model_config = ConfigDict(extra="forbid")

    goal: str = Field(
        ...,
        min_length=10,
        description="One-sentence description of the task objective.",
    )
    affected_layers: list[ArchitectureLayer] = Field(
        ...,
        min_length=1,
        description="Architecture layers this task will modify.",
    )
    scope_boundaries: list[str] = Field(
        default_factory=list,
        description=(
            "Glob patterns defining allowed file modifications. "
            "Empty means unrestricted (not recommended)."
        ),
    )
    forbidden_paths: list[str] = Field(
        default_factory=list,
        description="Glob patterns the task must not touch.",
    )
    quality_constraints: Annotated[
        list[str],
        Field(
            default_factory=list,
            description="Measurable quality requirements for the implementation.",
        ),
    ]
    acceptance_criteria: Annotated[
        list[str],
        Field(
            min_length=1,
            description="Conditions that define task completion.",
        ),
    ]
    requires_adr: bool | None = Field(
        default=None,
        description=(
            "Whether an ADR under decisions/ must exist before implementation. "
            "None = auto-infer."
        ),
    )
    requires_audit_update: bool | None = Field(
        default=None,
        description=(
            "Whether audit artifacts under audit_results/ must be updated. "
            "None = auto-infer."
        ),
    )
    commit_type: str = Field(
        default="",
        description=(
            "Expected conventional commit type (feat, fix, refactor, docs, test, chore). "
            "Empty means not yet determined."
        ),
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="Other tasks or ADR identifiers this task depends on.",
    )

    @model_validator(mode="after")
    def _infer_gate_requirements(self) -> TaskSpec:
        """Auto-detect gate requirements from affected layers."""
        affected_set = set(self.affected_layers)
        signal_layers = {
            ArchitectureLayer.SIGNALS,
            ArchitectureLayer.INGESTION,
            ArchitectureLayer.OUTPUT,
        }
        # Signal/ingestion/output changes require audit updates (Policy §18).
        if signal_layers & affected_set and self.requires_audit_update is None:
            self.requires_audit_update = True
        if self.requires_audit_update is None:
            self.requires_audit_update = False
        adr_layers = {
            ArchitectureLayer.SIGNALS,
            ArchitectureLayer.SCORING,
            ArchitectureLayer.OUTPUT,
        }
        # Signal/scoring/output changes require ADR.
        if adr_layers & affected_set and self.requires_adr is None:
            self.requires_adr = True
        if self.requires_adr is None:
            self.requires_adr = False
        return self

    @model_validator(mode="after")
    def _validate_blocking_semantics(self) -> TaskSpec:
        """Enforce blocking semantic constraints at model load time."""
        if self.requires_adr and not any("ADR" in dep.upper() for dep in self.depends_on):
            raise ValueError(
                "requires_adr is true but no ADR identifier in depends_on — "
                "specify the ADR number (e.g. 'ADR-034')."
            )
        if self.commit_type == "feat" and not self.acceptance_criteria:
            raise ValueError(
                "commit_type is 'feat' but no acceptance_criteria defined — "
                "feature evidence gate will require these."
            )
        return self

    @classmethod
    def from_yaml(cls, path: str | Path) -> TaskSpec:
        """Load a TaskSpec from YAML and run full semantic validation."""
        import yaml  # type: ignore[import-untyped]

        spec_path = Path(path)
        data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Expected a mapping in {spec_path}, got {type(data).__name__}.")
        spec = cls.model_validate(data)
        result = validate_task_spec(spec)
        if result.errors:
            raise ValueError(
                "TaskSpec contains blocking semantic issues: " + "; ".join(result.errors)
            )
        return spec


def validate_task_spec(spec: TaskSpec) -> TaskSpecValidationResult:
    """Validate a TaskSpec and return structured semantic validation results.

    Blocking issues are returned in ``errors`` and advisories in ``warnings``.

    Args:
        spec: The task specification to validate.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Check scope boundaries are set for non-trivial tasks
    if not spec.scope_boundaries and spec.affected_layers != [ArchitectureLayer.DOCS]:
        warnings.append(
            "scope_boundaries is empty — consider defining allowed file patterns "
            "to prevent unintended modifications."
        )

    # Check quality constraints exist for code changes
    code_layers = {
        ArchitectureLayer.SIGNALS,
        ArchitectureLayer.INGESTION,
        ArchitectureLayer.SCORING,
        ArchitectureLayer.OUTPUT,
        ArchitectureLayer.COMMANDS,
    }
    affected_set = set(spec.affected_layers)
    if code_layers & affected_set and not spec.quality_constraints:
        warnings.append(
            "quality_constraints is empty for a code change — "
            "define measurable quality requirements."
        )

    # Check commit_type consistency
    if spec.commit_type == "feat" and not spec.acceptance_criteria:
        errors.append(
            "commit_type is 'feat' but no acceptance_criteria defined — "
            "feature evidence gate will require these."
        )

    # Check ADR requirement awareness
    if spec.requires_adr and "ADR" not in " ".join(spec.depends_on):
        errors.append(
            "requires_adr is true but no ADR identifier in depends_on — "
            "specify the ADR number (e.g. 'ADR-034')."
        )

    # Validate commit_type values
    valid_types = {"feat", "fix", "refactor", "docs", "test", "chore", ""}
    if spec.commit_type not in valid_types:
        errors.append(
            f"commit_type '{spec.commit_type}' is not a valid conventional commit type. "
            f"Expected one of: {', '.join(sorted(valid_types - {''}))}."
        )

    # Warn when code layers are affected but tests layer is missing
    if code_layers & affected_set and ArchitectureLayer.TESTS not in spec.affected_layers:
        warnings.append(
            "Code layers affected but 'tests' not in affected_layers — "
            "consider adding tests to ensure coverage."
        )

    # Warn about very short acceptance criteria (likely vague)
    for criterion in spec.acceptance_criteria:
        if len(criterion.strip()) < 15:
            warnings.append(
                f"Acceptance criterion is very short ({len(criterion.strip())} chars): "
                f"'{criterion}' — may be too vague to verify."
            )

    return TaskSpecValidationResult(
        is_valid=not errors,
        errors=errors,
        warnings=warnings,
    )

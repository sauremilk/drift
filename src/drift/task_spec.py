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

from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, ClassVar

if TYPE_CHECKING:
    from drift.models._patch import PatchIntent

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

    model_config = ConfigDict(extra="forbid", frozen=True)
    CURRENT_SCHEMA_VERSION: ClassVar[int] = 1

    schema_version: int = Field(
        default=1,
        ge=1,
        description=(
            "Version of the serialized TaskSpec schema. "
            "Used for forward migrations during load."
        ),
    )

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

    @model_validator(mode="before")
    @classmethod
    def _infer_gate_requirements(cls, data: object) -> object:
        """Auto-detect gate requirements from affected layers before model creation."""
        if not isinstance(data, dict):
            return data

        candidate = dict(data)
        raw_layers = candidate.get("affected_layers", [])
        affected_set: set[ArchitectureLayer] = set()
        for layer in raw_layers if isinstance(raw_layers, list) else []:
            if isinstance(layer, ArchitectureLayer):
                affected_set.add(layer)
                continue
            if isinstance(layer, str):
                # Invalid strings are validated later by pydantic field validation.
                with suppress(ValueError):
                    affected_set.add(ArchitectureLayer(layer))

        signal_layers = {
            ArchitectureLayer.SIGNALS,
            ArchitectureLayer.INGESTION,
            ArchitectureLayer.OUTPUT,
        }
        # Signal/ingestion/output changes require audit updates (Policy §18).
        if candidate.get("requires_audit_update") is None:
            candidate["requires_audit_update"] = bool(signal_layers & affected_set)

        adr_layers = {
            ArchitectureLayer.SIGNALS,
            ArchitectureLayer.SCORING,
            ArchitectureLayer.OUTPUT,
        }
        # Signal/scoring/output changes require ADR.
        if candidate.get("requires_adr") is None:
            candidate["requires_adr"] = bool(adr_layers & affected_set)

        return candidate

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

    def to_patch_intent(
        self,
        task_id: str,
        session_id: str | None = None,
    ) -> PatchIntent:
        """Create a :class:`PatchIntent` from this task specification.

        Maps TaskSpec fields to PatchIntent fields:
        ``scope_boundaries`` → ``declared_files``,
        ``forbidden_paths`` → ``forbidden_paths``,
        ``quality_constraints`` → ``quality_constraints``,
        ``acceptance_criteria`` → ``acceptance_criteria``,
        ``goal`` → ``expected_outcome``.

        Args:
            task_id: Unique identifier for the patch transaction.
            session_id: Optional session ID for multi-turn workflows.
        """
        from drift.models._patch import BlastRadius, PatchIntent

        return PatchIntent(
            task_id=task_id,
            session_id=session_id,
            declared_files=list(self.scope_boundaries),
            forbidden_paths=list(self.forbidden_paths),
            expected_outcome=self.goal,
            blast_radius=BlastRadius.LOCAL,
            quality_constraints=list(self.quality_constraints),
            acceptance_criteria=list(self.acceptance_criteria),
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> TaskSpec:
        """Load a TaskSpec from YAML and run full semantic validation."""
        import yaml  # type: ignore[import-untyped]

        spec_path = Path(path)
        data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Expected a mapping in {spec_path}, got {type(data).__name__}.")
        spec = cls.from_dict_versioned(data)
        result = validate_task_spec(spec)
        if result.errors:
            raise ValueError(
                "TaskSpec contains blocking semantic issues: " + "; ".join(result.errors)
            )
        return spec

    @classmethod
    def from_dict_versioned(cls, data: dict[str, object]) -> TaskSpec:
        """Load TaskSpec data with schema-version migration support."""
        if not isinstance(data, dict):
            raise ValueError(f"Expected mapping data, got {type(data).__name__}.")

        migrated: dict[str, object] = dict(data)
        raw_version = migrated.get("schema_version", 1)
        if not isinstance(raw_version, int):
            raise ValueError("TaskSpec schema_version must be an integer.")
        if raw_version < 1:
            raise ValueError("TaskSpec schema_version must be >= 1.")
        if raw_version > cls.CURRENT_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported TaskSpec schema_version "
                f"{raw_version}; this drift version supports up to "
                f"{cls.CURRENT_SCHEMA_VERSION}."
            )

        version = raw_version
        while version < cls.CURRENT_SCHEMA_VERSION:
            migrated = cls._migrate_to_next_version(version, migrated)
            version += 1

        migrated["schema_version"] = cls.CURRENT_SCHEMA_VERSION
        return cls.model_validate(migrated)

    @classmethod
    def _migrate_to_next_version(
        cls,
        from_version: int,
        data: dict[str, object],
    ) -> dict[str, object]:
        """Apply one migration step to the immediate next schema version."""
        # No schema migration exists yet because v1 is the baseline.
        if from_version == 1 and cls.CURRENT_SCHEMA_VERSION == 1:
            return data
        raise ValueError(f"No TaskSpec migration registered for schema_version {from_version}.")


def validate_task_spec(spec: TaskSpec) -> TaskSpecValidationResult:
    """Validate a TaskSpec and return structured semantic validation results.

    Blocking issues are returned in ``errors`` and advisories in ``warnings``.

    Args:
        spec: The task specification to validate.
    """
    if not isinstance(spec, TaskSpec):
        raise TypeError(f"Expected TaskSpec, got {type(spec).__name__}")
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

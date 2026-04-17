"""Main DriftConfig class and YAML/TOML loader."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from drift.config._schema import (
    AgentObjective,
    AttributionConfig,
    BriefConfig,
    CalibrationConfig,
    DeferredArea,
    DocImplDriftConfig,
    FindingContextPolicy,
    GuidedThresholds,
    IntegrationsGlobalConfig,
    LanguagesConfig,
    PathOverride,
    PerformanceConfig,
    PluginConfig,
    PolicyConfig,
    RecommendationsConfig,
    SignalWeights,
    ThresholdsConfig,
)
from drift.config._schema import (
    GradeBandConfig as GradeBandConfig,
)
from drift.config._schema import (
    ScoringConfig as ScoringConfig,
)


def _default_includes() -> list[str]:
    """Return default include patterns, auto-extending for TypeScript when available."""
    patterns = ["**/*.py", "**/*.pyi"]
    # Avoid depending on ingestion module internals while still enabling
    # TS/JS includes when optional parser dependencies are installed.
    has_tree_sitter = importlib.util.find_spec("tree_sitter") is not None
    has_ts_grammar = importlib.util.find_spec("tree_sitter_typescript") is not None
    if has_tree_sitter and has_ts_grammar:
        patterns.extend(["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"])
    return patterns


class DriftConfig(BaseModel):
    """Main drift configuration, loaded from drift.yaml."""

    model_config = ConfigDict(extra="forbid")

    extends: str | None = Field(
        default=None,
        description=(
            "Name of a built-in preset to inherit from "
            "(e.g. 'vibe-coding', 'strict', 'fastapi', 'library', 'monorepo'). "
            "User-level fields override preset defaults."
        ),
    )

    include: list[str] = Field(default_factory=_default_includes)
    exclude: list[str] = Field(
        default_factory=lambda: [
            "**/node_modules/**",
            "**/__pycache__/**",
            "**/venv/**",
            "**/.venv/**",
            "**/.tmp_*venv*/**",
            "**/.env/**",
            "**/.conda/**",
            "**/.git/**",
            "**/dist/**",
            "**/build/**",
            "**/.tox/**",
            "**/.nox/**",
            "**/site-packages/**",
            "**/.pixi/**",
            "**/*.egg-info/**",
            "**/docs/**",
            "**/docs_src/**",
            "**/examples/**",
            "**/benchmarks/**",
            "**/benchmark_results/**",
            "**/tests/**",
            "**/scripts/**",
            "**/site/**",
        ]
    )
    policies: PolicyConfig = Field(default_factory=PolicyConfig)
    weights: SignalWeights = Field(default_factory=SignalWeights)
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
    guided_thresholds: GuidedThresholds | None = Field(
        default=None,
        description=(
            "Score band thresholds for guided-mode traffic light. "
            "When set via 'extends:', the profile's guided thresholds are applied automatically."
        ),
    )
    cache_dir: str = ".drift-cache"
    test_file_handling: str | None = Field(
        default=None,
        description=(
            "Global handling for findings in test files: "
            "exclude | reduce_severity | include. "
            "When null, each signal uses its built-in default."
        ),
    )
    signal_cache_dependency_scopes_enabled: bool = Field(
        default=True,
        description=(
            "Enable dependency-aware signal cache keying "
            "(file_local/module_wide/repo_wide/git_dependent)."
        ),
    )
    git_history_index_enabled: bool = Field(
        default=False,
        description=(
            "Enable persistent incremental git-history index under cache_dir "
            "to avoid full git-log parsing on repeated scans."
        ),
    )
    git_history_index_subdir: str = Field(
        default="git_history",
        description=(
            "Subdirectory inside cache_dir used for persistent git-history index "
            "artifacts (manifest + commits jsonl)."
        ),
    )
    fail_on: str = "high"
    context_dampening: float = 0.5
    fail_on_delta: float | None = None
    fail_on_delta_window: int = 5
    auto_calibrate: bool = True
    language: str | None = Field(
        default=None,
        description="ISO 639-1 output language for guided mode (e.g. 'de', 'en').",
    )
    embeddings_enabled: bool = True
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_batch_size: int = 64
    path_overrides: dict[str, PathOverride] = Field(default_factory=dict)
    deferred: list[DeferredArea] = Field(default_factory=list)
    finding_context: FindingContextPolicy = Field(default_factory=FindingContextPolicy)
    brief: BriefConfig = Field(default_factory=BriefConfig)
    plugins: PluginConfig = Field(default_factory=PluginConfig)
    dia: DocImplDriftConfig = Field(default_factory=DocImplDriftConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    calibration: CalibrationConfig = Field(default_factory=CalibrationConfig)
    recommendations: RecommendationsConfig = Field(default_factory=RecommendationsConfig)
    attribution: AttributionConfig = Field(default_factory=AttributionConfig)
    languages: LanguagesConfig = Field(default_factory=LanguagesConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    integrations: IntegrationsGlobalConfig = Field(
        default_factory=IntegrationsGlobalConfig,
        description=(
            "External tool integrations (hint / run / plugin tiers). "
            "Set enabled: true to activate. Default: disabled."
        ),
    )
    agent: AgentObjective | None = Field(
        default=None,
        description=(
            "Optional agent objective declaration. "
            "Helps drift provide targeted feedback aligned with the agent's task."
        ),
    )
    output_mode: Literal["full", "mirror"] = Field(
        default="full",
        description=(
            "Controls how much prescriptive guidance drift includes in API responses. "
            "'full' (default): all repair instructions, constraints, verify plans, "
            "and tool choreography. "
            "'mirror': diagnostic facts only — structural observations, scores, "
            "and deltas without prescribing what the agent should do."
        ),
    )

    @staticmethod
    def _find_config_file(repo_path: Path) -> Path | None:
        for name in ("drift.yaml", "drift.yml", ".drift.yaml"):
            candidate = repo_path / name
            if candidate.exists():
                return candidate
        # TOML config files (lower priority than YAML)
        drift_toml = repo_path / "drift.toml"
        if drift_toml.exists():
            return drift_toml
        pyproject = repo_path / "pyproject.toml"
        if pyproject.exists():
            return pyproject
        return None

    @classmethod
    def _load_toml(cls, config_path: Path) -> DriftConfig:
        """Load configuration from a TOML file (drift.toml or pyproject.toml)."""
        import tomllib

        raw = config_path.read_bytes()
        try:
            # Accept UTF-8 BOM to avoid first-run failures on editor-generated TOML files.
            data = tomllib.loads(raw.decode("utf-8-sig"))
        except Exception as exc:
            from drift.errors import DriftConfigError

            raise DriftConfigError(
                "DRIFT-1002",
                config_path=str(config_path),
                reason=str(exc),
                line="?",
                context=None,
            ) from exc

        # For pyproject.toml, extract [tool.drift] section
        if config_path.name == "pyproject.toml":
            data = data.get("tool", {}).get("drift", {})
            if not data:
                return cls()

        try:
            data = cls._apply_extends(data)
            return cls.model_validate(data)
        except ValidationError as exc:
            from drift.errors import DriftConfigError

            first: Any = exc.errors()[0] if exc.errors() else None
            loc = first.get("loc", ()) if first else ()
            field_path = ".".join(str(s) for s in loc) if loc else "unknown"
            reason = str(first.get("msg", str(exc))) if first else str(exc)
            raise DriftConfigError(
                "DRIFT-1001",
                config_path=str(config_path),
                field=field_path,
                reason=reason,
                line="?",
                context=None,
            ) from exc

    @staticmethod
    def _apply_extends(data: Any) -> dict[str, Any]:
        """Merge built-in preset defaults under user-supplied overrides.

        If *data* contains an ``extends`` key naming a registered profile,
        the profile's config dict is used as the base and *data* is merged on
        top (user wins).  Nested dicts (weights, thresholds, policies) are
        merged key-by-key; all other fields are replaced wholesale.
        """
        if not isinstance(data, dict):
            from drift.errors import DriftConfigError

            raise DriftConfigError(
                "DRIFT-1001",
                config_path="drift.yaml",
                field="root",
                reason="Top-level config must be a mapping/object.",
                line="?",
                context=None,
            )

        extends = data.get("extends")
        if not extends:
            return data

        from drift.profiles import PROFILES, get_profile

        try:
            profile = get_profile(extends)
        except KeyError as err:
            from drift.errors import DriftConfigError

            available = ", ".join(sorted(PROFILES))
            raise DriftConfigError(
                "DRIFT-1001",
                config_path="drift.yaml",
                field="extends",
                reason=(f"Unknown preset '{extends}'. Available: {available}"),
                line="?",
                context=None,
            ) from err

        # Build base dict from profile
        base: dict[str, Any] = {
            "weights": dict(profile.weights),
            "fail_on": profile.fail_on,
            "auto_calibrate": profile.auto_calibrate,
        }
        if profile.thresholds:
            base["thresholds"] = dict(profile.thresholds)
        if profile.policies:
            base["policies"] = dict(profile.policies)
        if profile.guided_thresholds:
            base["guided_thresholds"] = dict(profile.guided_thresholds)

        # Deep-merge: user data wins over preset base
        for key, value in data.items():
            if key == "extends":
                continue
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key] = {**base[key], **value}
            else:
                base[key] = value

        # Keep extends in the merged output so it is stored on the model
        base["extends"] = extends
        return base

    @classmethod
    def load(cls, repo_path: Path, config_path: Path | None = None) -> DriftConfig:
        if config_path is None:
            config_path = cls._find_config_file(repo_path)

        if config_path and config_path.exists():
            if config_path.suffix == ".toml":
                return cls._load_toml(config_path)

            raw = config_path.read_text(encoding="utf-8")

            try:
                data = yaml.safe_load(raw) or {}
            except yaml.YAMLError as exc:
                from drift.errors import DriftConfigError, yaml_context_snippet

                line = getattr(exc, "problem_mark", None)
                parse_lineno = (line.line + 1) if line else 1
                parse_context = yaml_context_snippet(raw, parse_lineno)
                raise DriftConfigError(
                    "DRIFT-1002",
                    config_path=str(config_path),
                    reason=str(exc),
                    line=parse_lineno,
                    context=parse_context,
                ) from exc

            try:
                data = cls._apply_extends(data)
                return cls.model_validate(data)
            except ValidationError as exc:
                from drift.errors import (
                    DriftConfigError,
                    _find_yaml_line,
                    yaml_context_snippet,
                )

                first: Any = exc.errors()[0] if exc.errors() else None
                loc = first.get("loc", ()) if first else ()
                field_path = ".".join(str(s) for s in loc) if loc else "unknown"
                reason = str(first.get("msg", str(exc))) if first else str(exc)
                validation_lineno = _find_yaml_line(raw, loc) if loc else None
                validation_context = (
                    yaml_context_snippet(raw, validation_lineno or 1) if raw else None
                )
                raise DriftConfigError(
                    "DRIFT-1001",
                    config_path=str(config_path),
                    field=field_path,
                    reason=reason,
                    line=validation_lineno or "?",
                    context=validation_context,
                ) from exc

        return cls()

    def severity_gate(self) -> str:
        return self.fail_on


def build_config_json_schema() -> dict[str, Any]:
    """Return the authoritative JSON Schema for drift configuration files."""
    schema = DriftConfig.model_json_schema(by_alias=True)
    schema.setdefault("$schema", "https://json-schema.org/draft/2020-12/schema")
    return schema

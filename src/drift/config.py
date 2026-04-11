"""Configuration loading and validation for Drift."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class LayerBoundary(BaseModel):
    """A single layer boundary rule."""

    name: str
    from_pattern: str = Field(alias="from")
    deny_import: list[str] = []

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class LazyImportRule(BaseModel):
    """Policy rule for enforcing lazy imports of selected modules."""

    name: str
    from_pattern: str = Field(alias="from")
    modules: list[str] = Field(default_factory=list)
    module_level_only: bool = True

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class PolicyConfig(BaseModel):
    """Policy configuration for enforcement rules."""

    model_config = ConfigDict(extra="forbid")

    error_handling: dict[str, Any] = Field(default_factory=dict)
    layer_boundaries: list[LayerBoundary] = Field(default_factory=list)
    max_pattern_variants: dict[str, int] = Field(default_factory=dict)
    ai_attribution: dict[str, Any] = Field(default_factory=dict)
    allowed_cross_layer: list[str] = Field(default_factory=list)
    lazy_import_rules: list[LazyImportRule] = Field(default_factory=list)
    omnilayer_dirs: list[str] = Field(default_factory=list)


class ThresholdsConfig(BaseModel):
    """Tunable thresholds for detection signals."""

    model_config = ConfigDict(extra="forbid")

    high_complexity: int = 10
    medium_complexity: int = 5
    min_function_loc: int = 15
    min_complexity: int = 8
    similarity_threshold: float = 0.80
    recency_days: int = 14
    volatility_z_threshold: float = 1.5
    ai_confidence_threshold: float = 0.50
    bem_min_handlers: int = 3
    tpd_min_test_functions: int = 5
    tpd_min_assertions_per_test: int = 1  # flag zero-assertion tests
    gcd_min_public_functions: int = 3
    gcd_max_nesting_depth: int = 4  # deep nesting threshold per function
    nbv_min_function_loc: int = 3  # ADR-008: ignore trivial stubs
    bat_density_threshold: float = 0.05  # ADR-008: markers per LOC
    bat_min_loc: int = 50  # ADR-008: skip tiny files
    ecm_max_files: int = 50  # ADR-008: perf guardrail
    ecm_lookback_commits: int = 20  # ADR-008: git history depth
    cxs_max_complexity: int = 15  # cognitive complexity threshold per function
    foe_max_imports: int = 15  # fan-out explosion: unique imports threshold
    dca_ignore_re_exports: bool = True  # dead-code: ignore __init__.py re-exports
    max_discovery_files: int = 10000  # safety guardrail for huge repos
    small_repo_module_threshold: int = 15  # adaptive dampening below this
    small_repo_min_findings: int = 2  # per-signal minimum to score
    diff_baseline_recommend_max_changed_files: int = 50
    diff_baseline_recommend_max_new_findings: int = 100
    diff_baseline_recommend_max_out_of_scope_findings: int = 50

    # PHR runtime validation (ADR-041)
    phr_runtime_validation: bool = False  # opt-in: import + hasattr check

    # Security-by-default thresholds
    hsc_min_entropy: float = 3.5  # Shannon entropy per char for secret detection
    hsc_min_length: int = 16  # minimum string length for entropy-based detection
    maz_public_endpoint_allowlist: list[str] = Field(
        default_factory=lambda: [
            "health",
            "healthcheck",
            "health_check",
            "ping",
            "ready",
            "readiness",
            "liveness",
            "metrics",
            "openapi",
            "docs",
            "redoc",
            "favicon",
            "robots",
            "sitemap",
            "schema",
            # Common intentionally-public endpoints (#148)
            "public",
            "anon",
            "anonymous",
            "root",
            "index",
            "manifest",
            "version",
            "status",
            "info",
            "pricing",
            "price",
            "security_txt",
            "wellknown",
            "well_known",
            "callback",
            "webhook",
            "csrf",
            "csp_report",
            "invite",
            "unsubscribe",
            "confirm",
            "verify_email",
            "reset_password",
            "register",
            "signup",
            "login",
            "logout",
            "oauth",
            "sso",
        ]
    )
    maz_dev_tool_paths: list[str] = Field(
        default_factory=lambda: [
            "debug",
            "internal",
            "dev",
            "devtools",
            "playground",
            "_debug",
            "__debug__",
        ]
    )


class SignalWeights(BaseModel):
    """Weights for each detection signal in composite scoring.

    Weights are normalised internally — they don't need to sum to 1.0,
    but a warning is emitted if they deviate significantly.

    Signals can be run in report-only mode by assigning weight 0.0.
    This keeps detection visible while removing score impact until
    precision/recall is sufficiently validated.
    """

    model_config = ConfigDict(extra="allow")  # Plugin signals add custom weight fields

    # Core signals (ablation-validated)
    pattern_fragmentation: float = 0.16
    architecture_violation: float = 0.16
    mutant_duplicate: float = 0.13
    explainability_deficit: float = 0.09
    temporal_volatility: float = 0.0
    system_misalignment: float = 0.08

    # Promoted from report-only (v0.7.0)
    doc_impl_drift: float = 0.04
    broad_exception_monoculture: float = 0.04
    test_polarity_deficit: float = 0.04
    guard_clause_deficit: float = 0.03
    cohesion_deficit: float = 0.01
    naming_contract_violation: float = 0.04
    bypass_accumulation: float = 0.03
    exception_contract_drift: float = 0.03
    co_change_coupling: float = 0.005

    # New signals — report-only until precision/recall validated
    ts_architecture: float = 0.0
    cognitive_complexity: float = 0.0
    circular_import: float = 0.0
    dead_code_accumulation: float = 0.0

    # Promoted from report-only (ADR-039: agent-safety signals)
    fan_out_explosion: float = 0.005
    hardcoded_secret: float = 0.01
    phantom_reference: float = 0.02

    # Security-by-default signals (ADR-039: activated for scoring)
    missing_authorization: float = 0.02
    insecure_default: float = 0.01

    def as_dict(self) -> dict[str, float]:
        return self.model_dump()


class PathOverride(BaseModel):
    """Per-path configuration overrides.

    Match paths using glob patterns (e.g. ``tests/**``, ``legacy/``).
    More specific patterns take precedence over broader ones.
    """

    model_config = ConfigDict(extra="forbid")

    weights: SignalWeights | None = None
    exclude_signals: list[str] = Field(default_factory=list)
    severity_gate: str | None = None


class DeferredArea(BaseModel):
    """A glob-matched area marked as known technical debt (not excluded).

    Unlike ``exclude``, deferred areas are still analysed.  Findings in
    deferred areas are tagged ``deferred=True`` so CI gates and reports
    can treat them differently.
    """

    model_config = ConfigDict(extra="forbid")

    pattern: str
    reason: str = ""
    review_by: str | None = None  # ISO date or sprint identifier


class FindingContextRule(BaseModel):
    """Classify findings by file path using glob patterns."""

    model_config = ConfigDict(extra="forbid")

    pattern: str
    context: str
    precedence: int = 0


class FindingContextPolicy(BaseModel):
    """Policy for finding-context classification and triage behavior."""

    model_config = ConfigDict(extra="forbid")

    rules: list[FindingContextRule] = Field(
        default_factory=lambda: [
            FindingContextRule(pattern="**/benchmarks/**", context="fixture", precedence=40),
            FindingContextRule(pattern="**/benchmark_results/**", context="fixture", precedence=40),
            FindingContextRule(pattern="**/corpus/**", context="fixture", precedence=40),
            FindingContextRule(pattern="**/fixtures/**", context="fixture", precedence=35),
            FindingContextRule(pattern="**/testdata/**", context="fixture", precedence=35),
            FindingContextRule(pattern="**/generated/**", context="generated", precedence=35),
            FindingContextRule(pattern="**/gen/**", context="generated", precedence=30),
            FindingContextRule(pattern="**/migrations/**", context="migration", precedence=30),
            FindingContextRule(pattern="**/docs/**", context="docs", precedence=20),
            FindingContextRule(pattern="**/docs_src/**", context="docs", precedence=20),
            FindingContextRule(pattern="**/site/**", context="docs", precedence=20),
        ]
    )
    non_operational_contexts: list[str] = Field(
        default_factory=lambda: ["fixture", "generated", "migration", "docs", "library"]
    )
    default_context: str = "production"


class AgentEffectivenessThresholds(BaseModel):
    """Thresholds for deterministic low-effect/high-churn warnings."""

    model_config = ConfigDict(extra="forbid")

    low_effect_resolved_per_changed_file: float = Field(default=0.25)
    low_effect_resolved_per_100_loc_changed: float = Field(default=0.5)
    high_churn_min_changed_files: int = Field(default=5)
    high_churn_min_loc_changed: int = Field(default=200)


class AgentObjective(BaseModel):
    """Declarative agent objective for drift.yaml.

    Allows agents to declare their goal, out-of-scope areas,
    and success criteria so drift can provide targeted feedback.

    Example drift.yaml::

        agent:
          goal: "Migrate payment module to Stripe API"
          out_of_scope:
            - "legacy/"
            - "tests/fixtures/"
          success_criteria:
            - "No new AVS findings in src/billing/"
    """

    model_config = ConfigDict(extra="forbid")

    goal: str = Field(
        default="",
        description="Natural-language description of the agent's current task.",
    )
    strict_guardrails: bool = Field(
        default=False,
        description=(
            "When true, MCP orchestration enforces strict preconditions and "
            "blocks unsafe tool transitions with recovery hints."
        ),
    )
    out_of_scope: list[str] = Field(
        default_factory=list,
        description="Glob patterns or paths the agent should not modify or analyze.",
    )
    success_criteria: list[str] = Field(
        default_factory=list,
        description="Conditions that define task completion (human-readable).",
    )
    effectiveness_thresholds: AgentEffectivenessThresholds = Field(
        default_factory=AgentEffectivenessThresholds,
        description=(
            "Thresholds used for deterministic effectiveness warnings "
            "(e.g. low_effect_high_churn)."
        ),
    )


class BriefConfig(BaseModel):
    """Configuration for ``drift brief`` pre-task briefings."""

    model_config = ConfigDict(extra="forbid")

    scope_aliases: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Keyword → path mapping for scope resolution. "
            "Example: {payment: src/billing/, auth: src/auth/}"
        ),
    )


def _default_includes() -> list[str]:
    """Return default include patterns, auto-extending for TypeScript when available."""
    patterns = ["**/*.py"]
    # Avoid depending on ingestion module internals while still enabling
    # TS/JS includes when optional parser dependencies are installed.
    has_tree_sitter = importlib.util.find_spec("tree_sitter") is not None
    has_ts_grammar = importlib.util.find_spec("tree_sitter_typescript") is not None
    if has_tree_sitter and has_ts_grammar:
        patterns.extend(["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"])
    return patterns


class CalibrationConfig(BaseModel):
    """Configuration for per-repo signal calibration (ADR-035).

    When enabled, drift collects and uses feedback evidence to compute
    project-specific signal weights via Bayesian weight calibration.

    Example drift.yaml::

        calibration:
          enabled: true
          min_samples: 20
          bug_labels:
            - bug
            - regression
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(
        default=False,
        description="Enable per-repo signal calibration.",
    )
    min_samples: int = Field(
        default=20,
        description=(
            "Minimum TP+FP observations per signal for full confidence. "
            "Below this, calibration blends toward default weights."
        ),
    )
    correlation_window_days: int = Field(
        default=30,
        description="Days after a scan to look for defect-fix commits (TP evidence).",
    )
    decay_days: int = Field(
        default=90,
        description="Days after which the calibration profile is considered stale.",
    )
    weak_fp_window_days: int = Field(
        default=60,
        description="Days without a defect-fix → weak FP evidence.",
    )
    fn_boost_factor: float = Field(
        default=0.1,
        description=(
            "How much to boost weight for signals with high false-negative rate "
            "(0.0 disables FN boosting, max 1.0)."
        ),
    )
    github_token: str | None = Field(
        default=None,
        description="GitHub API token for issue/PR correlation (or use DRIFT_GITHUB_TOKEN env).",
    )
    bug_labels: list[str] = Field(
        default_factory=lambda: ["bug", "regression", "defect"],
        description="Issue labels that identify bug reports for GitHub correlation.",
    )
    auto_recalibrate: bool = Field(
        default=False,
        description="Automatically recalibrate after each drift analyze run.",
    )
    feedback_path: str = Field(
        default=".drift/feedback.jsonl",
        description="Path to the feedback JSONL file (relative to repo root).",
    )
    history_dir: str = Field(
        default=".drift/history",
        description="Directory for scan history snapshots (relative to repo root).",
    )
    max_snapshots: int = Field(
        default=20,
        description="Maximum number of scan snapshots to retain.",
    )
    threshold_adaptation_enabled: bool = Field(
        default=False,
        description=(
            "Enable adaptive threshold adjustment per signal based on "
            "feedback metrics.  Experimental — disabled by default."
        ),
    )


class AttributionConfig(BaseModel):
    """Configuration for causal attribution enrichment (ADR-034).

    When enabled, findings are enriched with git-blame provenance data
    identifying the commit, author, and date that introduced the drifting code.

    Example drift.yaml::

        attribution:
          enabled: true
          timeout_per_file_seconds: 3.0
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(
        default=False,
        description="Enable git-blame-based causal attribution on findings.",
    )
    cache_enabled: bool = Field(
        default=True,
        description="Cache blame results per file content hash.",
    )
    timeout_per_file_seconds: float = Field(
        default=3.0,
        description="Maximum seconds for a single git-blame subprocess call.",
    )
    max_parallel_workers: int = Field(
        default=4,
        description="Thread pool size for parallel blame calls.",
    )
    include_branch_hint: bool = Field(
        default=True,
        description="Attempt to extract branch name from merge-commit messages.",
    )


class PluginConfig(BaseModel):
    """Configuration for Drift plugins.

    Plugins are discovered via Python entry_points (see drift.plugins).
    This configuration section allows selectively disabling specific plugins.

    Example drift.yaml::

        plugins:
          disabled:
            - my_broken_plugin
    """

    model_config = ConfigDict(extra="forbid")

    disabled: list[str] = Field(
        default_factory=list,
        description="List of plugin entry-point names to skip at discovery time.",
    )


class DocImplDriftConfig(BaseModel):
    """DIA-specific configuration for doc-implementation drift detection."""

    model_config = ConfigDict(extra="forbid")

    extra_auxiliary_dirs: list[str] = Field(default_factory=list)
    extra_context_keywords: list[str] = Field(default_factory=list)


class LanguagesConfig(BaseModel):
    """Per-language scanning settings (drift.yaml → ``languages:``)."""

    model_config = ConfigDict(extra="forbid")

    typescript: bool = Field(
        default=True,
        description=(
            "Enable TypeScript/TSX/JS/JSX analysis. "
            "Requires drift-analyzer[typescript] (tree-sitter). "
            "Set to false to skip TS files even when tree-sitter is installed."
        ),
    )


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
        default=False,
        description=(
            "Enable dependency-aware signal cache keying "
            "(file_local/module_wide/repo_wide/git_dependent)."
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
    calibration: CalibrationConfig = Field(default_factory=CalibrationConfig)
    attribution: AttributionConfig = Field(default_factory=AttributionConfig)
    languages: LanguagesConfig = Field(default_factory=LanguagesConfig)
    agent: AgentObjective | None = Field(
        default=None,
        description=(
            "Optional agent objective declaration. "
            "Helps drift provide targeted feedback aligned with the agent's task."
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
                reason=(
                    f"Unknown preset '{extends}'. "
                    f"Available: {available}"
                ),
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
            base.setdefault("thresholds", {})
            base["thresholds"]["guided"] = dict(profile.guided_thresholds)

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


# ---------------------------------------------------------------------------
# Signal abbreviation map & CLI filter helpers
# ---------------------------------------------------------------------------

def _build_signal_abbrev() -> dict[str, str]:
    """Build abbrev→signal_id map from the central registry, with static fallback."""
    try:
        from drift.signal_registry import get_abbrev_map

        return get_abbrev_map()
    except ImportError:
        pass
    # Static fallback for environments where signals haven't been imported yet
    return {
        "PFS": "pattern_fragmentation",
        "AVS": "architecture_violation",
        "MDS": "mutant_duplicate",
        "EDS": "explainability_deficit",
        "TVS": "temporal_volatility",
        "SMS": "system_misalignment",
        "DIA": "doc_impl_drift",
        "BEM": "broad_exception_monoculture",
        "TPD": "test_polarity_deficit",
        "GCD": "guard_clause_deficit",
        "COD": "cohesion_deficit",
        "NBV": "naming_contract_violation",
        "BAT": "bypass_accumulation",
        "ECM": "exception_contract_drift",
        "CCC": "co_change_coupling",
        "TSA": "ts_architecture",
        "CXS": "cognitive_complexity",
        "FOE": "fan_out_explosion",
        "CIR": "circular_import",
        "DCA": "dead_code_accumulation",
        "MAZ": "missing_authorization",
        "ISD": "insecure_default",
        "HSC": "hardcoded_secret",
        "PHR": "phantom_reference",
    }


SIGNAL_ABBREV: dict[str, str] = _build_signal_abbrev()


def resolve_signal_names(raw: str) -> list[str]:
    """Resolve comma-separated signal IDs (abbreviations or full names) to full names.

    Raises ValueError for unknown signal IDs.
    """
    all_known = set(SignalWeights.model_fields.keys())
    result: list[str] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        upper = token.upper()
        if upper in SIGNAL_ABBREV:
            result.append(SIGNAL_ABBREV[upper])
        elif token.lower() in all_known:
            result.append(token.lower())
        else:
            abbrevs = ", ".join(sorted(SIGNAL_ABBREV))
            raise ValueError(
                f"Unknown signal: {token!r}. "
                f"Use abbreviations ({abbrevs}) or full names."
            )
    return result


def apply_signal_filter(
    cfg: DriftConfig,
    select: str | None,
    ignore: str | None,
) -> None:
    """Modify config weights based on --select / --ignore CLI flags.

    --select: only these signals are active (all others set to weight 0).
    --ignore: these signals are deactivated (weight 0).
    If both are given, --select is applied first, then --ignore removes
    from the selected set.
    """
    if select:
        selected = set(resolve_signal_names(select))
        for key in SignalWeights.model_fields:
            if key not in selected:
                setattr(cfg.weights, key, 0.0)

    if ignore:
        ignored = set(resolve_signal_names(ignore))
        for key in ignored:
            setattr(cfg.weights, key, 0.0)

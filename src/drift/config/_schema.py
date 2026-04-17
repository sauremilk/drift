"""Pydantic schema models for Drift configuration."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Integrations
# ---------------------------------------------------------------------------


class IntegrationSeverityMap(BaseModel):
    """Maps external tool severity levels to Drift Severity values."""

    model_config = ConfigDict(extra="allow")

    error: str = "high"
    warning: str = "medium"
    info: str = "info"
    note: str = "info"


class IntegrationConfig(BaseModel):
    """Configuration for a single external tool integration.

    Example drift.yaml::

        integrations:
          - name: superpowers
            tier: run
            trigger_signals:
              - pattern_fragmentation
            command: ["superpowers", "check", "--format", "json", "{repo_path}"]
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Unique identifier for this integration.")
    tier: Literal["hint", "run", "plugin"] = Field(
        description="Integration tier: hint (report only), run (subprocess), plugin (YAML)."
    )
    enabled: bool = Field(default=True)
    trigger_signals: list[str] = Field(
        default_factory=lambda: ["*"],
        description=(
            "List of signal types that activate this integration. "
            "Use '*' to trigger on any finding."
        ),
    )
    command: list[str] = Field(
        default_factory=list,
        description=(
            "Command to invoke (run/plugin tiers). "
            "Use {repo_path} as placeholder for the repository root."
        ),
    )
    timeout_seconds: int = Field(default=30, ge=1)
    output_format: Literal["json", "text"] = Field(default="json")
    hint_text: str | None = Field(
        default=None,
        description="Static hint text to render in reports (hint tier).",
    )
    severity_map: IntegrationSeverityMap = Field(
        default_factory=IntegrationSeverityMap,
        description="Mapping of external tool severity levels to Drift severity values.",
    )


class IntegrationsGlobalConfig(BaseModel):
    """Global integrations section in drift.yaml.

    Example::

        integrations:
          enabled: false   # opt-in: set to true to activate
          adapters:
            - name: superpowers
              tier: run
              ...
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(
        default=False,
        description=(
            "Global switch. Must be set to true to run any integration. "
            "Default false — explicit opt-in required."
        ),
    )
    adapters: list[IntegrationConfig] = Field(default_factory=list)


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
            # A2A (Agent-to-Agent) protocol — always intentionally public (#391)
            "a2a",
            "agent_card",
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

    # TypeScript quality signals
    type_safety_bypass: float = 0.0

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
            FindingContextRule(pattern="**/work_artifacts/**", context="fixture", precedence=45),
            FindingContextRule(pattern="**/audit_results/**", context="fixture", precedence=45),
            FindingContextRule(pattern="**/benchmarks/**", context="fixture", precedence=40),
            FindingContextRule(pattern="**/benchmark_results/**", context="fixture", precedence=40),
            FindingContextRule(pattern="**/corpus/**", context="fixture", precedence=40),
            FindingContextRule(pattern="**/fixtures/**", context="fixture", precedence=35),
            FindingContextRule(pattern="**/testdata/**", context="fixture", precedence=35),
            FindingContextRule(pattern="**/archive/**", context="fixture", precedence=35),
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
            "Thresholds used for deterministic effectiveness warnings (e.g. low_effect_high_churn)."
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


class PerformanceConfig(BaseModel):
    """Worker tuning controls for analysis pipeline execution."""

    model_config = ConfigDict(extra="forbid")

    worker_strategy: Literal["fixed", "auto"] = Field(
        default="fixed",
        description=(
            "Worker resolution strategy. 'fixed' uses CPU fallback (or env/CLI override). "
            "'auto' applies conservative tuning based on repository size, file types, "
            "and I/O proxy load."
        ),
    )
    load_profile: Literal["conservative"] = Field(
        default="conservative",
        description="Auto-tuning profile. Initial rollout supports conservative only.",
    )
    min_workers: int = Field(
        default=2,
        ge=1,
        description="Lower clamp for auto-tuned worker counts.",
    )
    max_workers: int = Field(
        default=16,
        ge=1,
        description="Upper clamp for auto-tuned worker counts.",
    )
    small_repo_file_threshold: int = Field(
        default=40,
        ge=1,
        description=(
            "Repos at or below this file count are downscaled to avoid "
            "over-parallelization."
        ),
    )
    io_heavy_non_parser_ratio: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description=(
            "When the non-parser file share exceeds this ratio, auto mode dampens workers "
            "to account for higher I/O overhead."
        ),
    )
    large_file_size_bytes: int = Field(
        default=250_000,
        ge=1,
        description="Files above this size are considered I/O-heavy for conservative tuning.",
    )
    large_file_ratio_threshold: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Share of large files that triggers additional worker dampening.",
    )


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
    shared_feedback_path: str | None = Field(
        default=None,
        description=(
            "Optional team-shared feedback JSONL path (relative to repo root). "
            "When set, mark/calibrate commands read and write this path instead "
            "of calibration.feedback_path."
        ),
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


class RecommendationsConfig(BaseModel):
    """Configuration for the adaptive recommendation engine (ARE).

    Controls outcome tracking, effort calibration, and recommendation
    refinement.  All features are opt-in (``enabled: false`` by default).

    Example drift.yaml::

        recommendations:
          enabled: true
          archive_after_days: 180
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(
        default=False,
        description="Enable adaptive recommendation engine (outcome tracking + reward chain).",
    )
    outcome_path: str = Field(
        default=".drift/outcomes.jsonl",
        description="Path to the outcome JSONL file (relative to repo root).",
    )
    calibration_path: str = Field(
        default=".drift/effort_calibration.json",
        description="Path to the effort calibration JSON file (relative to repo root).",
    )
    archive_after_days: int = Field(
        default=180,
        description="Archive resolved outcomes older than this many days.",
    )
    min_calibration_samples: int = Field(
        default=10,
        description="Minimum resolved outcomes per signal type before effort calibration kicks in.",
    )
    refinement_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Recommendations with reward >= this threshold skip refinement.",
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


class GradeBandConfig(BaseModel):
    """A single grade band entry for the composite drift score.

    Grade bands map score ranges to letter grades and human-readable labels.
    Thresholds are evaluated in order; the first entry whose ``threshold``
    exceeds the score is selected.

    Example::

        - threshold: 0.20
          grade: A
          label: "Excellent"
    """

    model_config = ConfigDict(extra="forbid")

    threshold: float = Field(gt=0.0, description="Upper boundary (exclusive) for this grade.")
    grade: str = Field(description="Letter grade, e.g. 'A', 'B', …, 'F'.")
    label: str = Field(description="Human-readable label, e.g. 'Excellent'.")


class ScoringConfig(BaseModel):
    """Tunable scoring-engine parameters (drift.yaml → ``scoring:``)

    All settings default to the validated ADR-003/ADR-041 values and are
    backward-compatible — changing these knobs only affects repos that
    explicitly set them.

    Example drift.yaml::

        scoring:
          dampening_k: 10
          breadth_cap: 3.0
          feedback_blend_alpha: 0.3
    """

    model_config = ConfigDict(extra="forbid")

    dampening_k: int = Field(
        default=20,
        ge=1,
        description=(
            "Count-dampening constant for signal aggregation (ADR-041). "
            "Finding counts above this value produce a dampening factor near 1.0. "
            "Lower values increase sensitivity to high-finding signals."
        ),
    )
    breadth_cap: float = Field(
        default=4.0,
        gt=0.0,
        description=(
            "Ceiling for the log-based breadth multiplier applied to impact scores (ADR-041). "
            "Prevents very large related-file clusters from inflating scores unboundedly."
        ),
    )
    grade_bands: list[GradeBandConfig] = Field(
        default_factory=lambda: [
            GradeBandConfig(threshold=0.20, grade="A", label="Excellent"),
            GradeBandConfig(threshold=0.40, grade="B", label="Good"),
            GradeBandConfig(threshold=0.60, grade="C", label="Moderate Drift"),
            GradeBandConfig(threshold=0.80, grade="D", label="Significant Drift"),
            GradeBandConfig(threshold=1.01, grade="F", label="Critical Drift"),
        ],
        description=(
            "Ordered list of score thresholds that map drift scores to letter grades. "
            "Each entry selects the grade when ``score < threshold``. "
            "The last entry should have a threshold above 1.0 as a catch-all."
        ),
    )
    feedback_blend_alpha: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Blend factor for feedback-informed weight adjustment. "
            "0.0 = pure auto-calibrate from finding distribution (default). "
            "1.0 = weights fully driven by persisted feedback metrics. "
            "Values between 0 and 1 linearly interpolate both approaches. "
            "Effective only when ``calibration.enabled = true`` and feedback "
            "data exists at ``calibration.feedback_path``."
        ),
    )


class GuidedThresholds(BaseModel):
    """Score band thresholds for guided-mode traffic light (green / yellow / red).

    These thresholds determine how the composite drift score maps to a
    traffic-light status in ``drift status`` / guided mode.
    """

    model_config = ConfigDict(extra="forbid")

    green_max: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Scores at or below this value are shown as green (healthy).",
    )
    yellow_max: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description=(
            "Scores above green_max and at or below this value are shown as yellow (caution)."
        ),
    )

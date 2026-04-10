"""Core data models for Drift analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import datetime
    from pathlib import Path

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingStatus(StrEnum):
    ACTIVE = "active"
    SUPPRESSED = "suppressed"
    RESOLVED = "resolved"


class SignalType(StrEnum):
    PATTERN_FRAGMENTATION = "pattern_fragmentation"
    ARCHITECTURE_VIOLATION = "architecture_violation"
    MUTANT_DUPLICATE = "mutant_duplicate"
    EXPLAINABILITY_DEFICIT = "explainability_deficit"
    DOC_IMPL_DRIFT = "doc_impl_drift"
    TEMPORAL_VOLATILITY = "temporal_volatility"
    SYSTEM_MISALIGNMENT = "system_misalignment"
    BROAD_EXCEPTION_MONOCULTURE = "broad_exception_monoculture"
    TEST_POLARITY_DEFICIT = "test_polarity_deficit"
    GUARD_CLAUSE_DEFICIT = "guard_clause_deficit"
    COHESION_DEFICIT = "cohesion_deficit"
    NAMING_CONTRACT_VIOLATION = "naming_contract_violation"  # ADR-008
    BYPASS_ACCUMULATION = "bypass_accumulation"  # ADR-008
    EXCEPTION_CONTRACT_DRIFT = "exception_contract_drift"  # ADR-008
    CO_CHANGE_COUPLING = "co_change_coupling"
    TS_ARCHITECTURE = "ts_architecture"
    COGNITIVE_COMPLEXITY = "cognitive_complexity"
    FAN_OUT_EXPLOSION = "fan_out_explosion"
    CIRCULAR_IMPORT = "circular_import"
    DEAD_CODE_ACCUMULATION = "dead_code_accumulation"
    MISSING_AUTHORIZATION = "missing_authorization"
    INSECURE_DEFAULT = "insecure_default"
    HARDCODED_SECRET = "hardcoded_secret"
    PHANTOM_REFERENCE = "phantom_reference"
    TYPE_SAFETY_BYPASS = "type_safety_bypass"


class PatternCategory(StrEnum):
    ERROR_HANDLING = "error_handling"
    DATA_ACCESS = "data_access"
    API_ENDPOINT = "api_endpoint"
    CACHING = "caching"
    LOGGING = "logging"
    TESTING = "testing"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    RETURN_PATTERN = "return_pattern"
    REACT_HOOK = "react_hook"


# ---------------------------------------------------------------------------
# Ingestion Models
# ---------------------------------------------------------------------------


@dataclass
class FileInfo:
    path: Path
    language: str
    size_bytes: int
    line_count: int = 0


@dataclass
class FunctionInfo:
    name: str
    file_path: Path
    start_line: int
    end_line: int
    language: str
    complexity: int = 0
    loc: int = 0
    parameters: list[str] = field(default_factory=list)
    return_type: str | None = None
    decorators: list[str] = field(default_factory=list)
    has_docstring: bool = False
    body_hash: str = ""
    ast_fingerprint: dict[str, Any] = field(default_factory=dict)
    is_exported: bool = False


@dataclass
class ClassInfo:
    name: str
    file_path: Path
    start_line: int
    end_line: int
    language: str
    bases: list[str] = field(default_factory=list)
    methods: list[FunctionInfo] = field(default_factory=list)
    has_docstring: bool = False
    is_interface: bool = False


@dataclass
class ImportInfo:
    source_file: Path
    imported_module: str
    imported_names: list[str]
    line_number: int
    is_relative: bool = False
    is_module_level: bool = True


@dataclass
class PatternInstance:
    """A single occurrence of a recognized code pattern."""

    category: PatternCategory
    file_path: Path
    function_name: str
    start_line: int
    end_line: int
    fingerprint: dict[str, Any] = field(default_factory=dict)
    variant_id: str = ""


@dataclass
class ParseResult:
    """Result of parsing a single source file."""

    file_path: Path
    language: str
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    imports: list[ImportInfo] = field(default_factory=list)
    patterns: list[PatternInstance] = field(default_factory=list)
    line_count: int = 0
    parse_errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Git Models
# ---------------------------------------------------------------------------


@dataclass
class CommitInfo:
    hash: str
    author: str
    email: str
    timestamp: datetime.datetime
    message: str
    files_changed: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0
    is_ai_attributed: bool = False
    ai_confidence: float = 0.0
    coauthors: list[str] = field(default_factory=list)


@dataclass
class FileHistory:
    """Git history statistics for a single file."""

    path: Path
    total_commits: int = 0
    unique_authors: int = 0
    ai_attributed_commits: int = 0
    change_frequency_30d: float = 0.0
    defect_correlated_commits: int = 0
    last_modified: datetime.datetime | None = None
    first_seen: datetime.datetime | None = None


# ---------------------------------------------------------------------------
# Attribution Models (ADR-034)
# ---------------------------------------------------------------------------


@dataclass
class BlameLine:
    """A single line result from git blame --porcelain."""

    line_no: int
    commit_hash: str
    author: str
    email: str
    date: datetime.date
    content: str = ""


@dataclass
class Attribution:
    """Causal provenance for a finding — who introduced the drifting code.

    Populated by the attribution enrichment pipeline when
    ``attribution.enabled`` is set in drift.yaml.
    """

    commit_hash: str
    author: str
    email: str
    date: datetime.date
    branch_hint: str | None = None
    ai_attributed: bool = False
    ai_confidence: float = 0.0
    commit_message_summary: str = ""


# ---------------------------------------------------------------------------
# Shared Helpers
# ---------------------------------------------------------------------------


def severity_for_score(score: float) -> Severity:
    """Map a 0.0-1.0 drift score to a severity level."""
    if score >= 0.8:
        return Severity.CRITICAL
    if score >= 0.6:
        return Severity.HIGH
    if score >= 0.4:
        return Severity.MEDIUM
    if score >= 0.2:
        return Severity.LOW
    return Severity.INFO


# ---------------------------------------------------------------------------
# Analysis Models
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    """A single detected issue."""

    signal_type: str  # SignalType value for core signals, arbitrary str for plugins
    severity: Severity
    score: float
    title: str
    description: str
    file_path: Path | None = None
    start_line: int | None = None
    end_line: int | None = None
    symbol: str | None = None
    related_files: list[Path] = field(default_factory=list)
    commit_hash: str | None = None
    ai_attributed: bool = False
    fix: str | None = None
    impact: float = 0.0
    score_contribution: float = 0.0
    deferred: bool = False
    status: FindingStatus = FindingStatus.ACTIVE
    status_set_by: str | None = None
    status_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    rule_id: str | None = None
    attribution: Attribution | None = None

    def __post_init__(self) -> None:
        if self.rule_id is None:
            self.rule_id = str(self.signal_type)
        # Ensure machine-readable location is always populated when a file
        # is known — agents cannot parse file paths from free-text fields.
        if self.file_path is not None and self.start_line is None:
            self.start_line = 1


@dataclass
class AnalyzerWarning:
    """A non-finding diagnostic emitted by a signal."""

    signal_type: str
    message: str
    skipped: bool = True


@dataclass
class ModuleScore:
    """Drift score for a single module (directory)."""

    path: Path
    drift_score: float
    signal_scores: dict[str, float] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    file_count: int = 0
    function_count: int = 0
    ai_ratio: float = 0.0

    @property
    def severity(self) -> Severity:
        return severity_for_score(self.drift_score)


@dataclass
class TrendContext:
    """Temporal context attached to every analysis result (ADR-005)."""

    previous_score: float | None
    delta: float | None
    direction: str  # "improving" | "stable" | "degrading" | "baseline"
    recent_scores: list[float]
    history_depth: int
    transition_ratio: float


@dataclass
class RepoAnalysis:
    """Complete analysis result for a repository."""

    repo_path: Path
    analyzed_at: datetime.datetime
    drift_score: float
    module_scores: list[ModuleScore] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    suppressed_findings: list[Finding] = field(default_factory=list)
    pattern_catalog: dict[PatternCategory, list[PatternInstance]] = field(default_factory=dict)
    total_files: int = 0
    total_functions: int = 0
    ai_attributed_ratio: float = 0.0
    analysis_duration_seconds: float = 0.0
    commits: list[CommitInfo] = field(default_factory=list)
    file_histories: dict[str, FileHistory] = field(default_factory=dict)
    suppressed_count: int = 0
    context_tagged_count: int = 0
    baseline_new_count: int | None = None
    baseline_matched_count: int | None = None
    trend: TrendContext | None = None
    analysis_status: str = "complete"  # "complete" | "degraded"
    degradation_causes: list[str] = field(default_factory=list)
    degradation_components: list[str] = field(default_factory=list)
    degradation_events: list[dict[str, Any]] = field(default_factory=list)
    ai_tools_detected: list[str] = field(default_factory=list)
    skipped_files: int = 0
    skipped_languages: dict[str, int] = field(default_factory=dict)
    preflight: Any | None = None
    analyzer_warnings: list[AnalyzerWarning] = field(default_factory=list)

    @property
    def severity(self) -> Severity:
        return severity_for_score(self.drift_score)

    @property
    def is_degraded(self) -> bool:
        return self.analysis_status == "degraded"

    @property
    def is_fully_reliable(self) -> bool:
        return not self.is_degraded

    def findings_by_severity(self, severity: Severity) -> list[Finding]:
        return [f for f in self.findings if f.severity == severity]


# ---------------------------------------------------------------------------
# Agent Task Model (agent-tasks output format)
# ---------------------------------------------------------------------------


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
    complexity: str = "medium"
    expected_effect: str = ""
    success_criteria: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    # Phase 1: Automation fitness classification
    automation_fit: str = "medium"  # "high" | "medium" | "low"
    review_risk: str = "medium"  # "low" | "medium" | "high"
    change_scope: str = "local"  # "local" | "module" | "cross-module"
    verification_strength: str = "moderate"  # "strong" | "moderate" | "weak"
    # Phase 2: Do-not-over-fix guardrails
    constraints: list[str] = field(default_factory=list)
    # Phase 4: Signal-specific repair maturity
    repair_maturity: str = "experimental"  # "verified" | "experimental" | "indirect-only"
    # Negative context: anti-patterns the agent must NOT reproduce
    negative_context: list[NegativeContext] = field(default_factory=list)
    # Expected score reduction when this task is resolved
    expected_score_delta: float = 0.0
    # ADR-025 Phase A: Task-graph fields for orchestration
    blocks: list[str] = field(default_factory=list)  # inverse of depends_on
    batch_group: str | None = None  # cluster ID for co-fixable tasks
    preferred_order: int = 0  # topological sort index within session
    parallel_with: list[str] = field(default_factory=list)  # task IDs safe to run concurrently


# ---------------------------------------------------------------------------
# Negative Context Model (anti-pattern feed for coding agents)
# ---------------------------------------------------------------------------


class NegativeContextCategory(StrEnum):
    """Category of anti-pattern detected by drift signals."""

    SECURITY = "security"
    ERROR_HANDLING = "error_handling"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    NAMING = "naming"
    COMPLEXITY = "complexity"
    COMPLETENESS = "completeness"


class NegativeContextScope(StrEnum):
    """Scope at which a negative context item applies."""

    FILE = "file"
    MODULE = "module"
    REPO = "repo"


@dataclass
class NegativeContext:
    """An anti-pattern warning derived from drift findings.

    Agents consume these items as "what NOT to do" context before generating
    code.  Each item is deterministically derived from signal findings —
    no LLM involved.
    """

    anti_pattern_id: str
    category: NegativeContextCategory
    source_signal: str
    severity: Severity
    scope: NegativeContextScope
    description: str
    forbidden_pattern: str  # concrete code anti-example
    canonical_alternative: str  # what to do instead
    affected_files: list[str] = field(default_factory=list)
    confidence: float = 1.0
    rationale: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

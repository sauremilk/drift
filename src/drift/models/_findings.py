"""Finding, analysis result, and scoring data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from drift.models._enums import FindingStatus, Severity, severity_for_score

if TYPE_CHECKING:
    import datetime
    from pathlib import Path

    # PatternCategory is also needed for the type annotation in RepoAnalysis,
    # but it is already available at runtime via _enums — import here for
    # TYPE_CHECKING completeness only.
    from drift.models._enums import PatternCategory
    from drift.models._git import Attribution, CommitInfo, FileHistory
    from drift.models._parse import PatternInstance


# ---------------------------------------------------------------------------
# Logical Location (AST-based)
# ---------------------------------------------------------------------------


def _validate_unit_interval(value: float, field_name: str) -> None:
    """Validate a normalized score field constrained to [0.0, 1.0]."""
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"{field_name} must be in [0.0, 1.0], got {value}")


@dataclass
class LogicalLocation:
    """AST-based logical location for a finding.

    Provides stable, line-number-independent coordinates that survive
    code edits — enabling autonomous agents to identify the affected
    code element even after preceding modifications shift line numbers.

    Field semantics follow SARIF v2.1.0 §3.33.
    """

    fully_qualified_name: str  # e.g. "src.api.auth.AuthService.login"
    name: str  # e.g. "login"
    kind: str  # "function" | "method" | "class" | "module"
    class_name: str | None = None  # e.g. "AuthService"
    namespace: str | None = None  # e.g. "src.api.auth"


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
    logical_location: LogicalLocation | None = None
    language: str | None = None
    finding_context: str | None = None

    #: Suffix → language for auto-inference (kept minimal to avoid imports).
    _LANG_MAP: ClassVar[dict[str, str]] = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".js": "javascript",
        ".jsx": "jsx",
    }

    def __post_init__(self) -> None:
        _validate_unit_interval(self.score, "Finding.score")
        _validate_unit_interval(self.impact, "Finding.impact")
        if self.rule_id is None:
            self.rule_id = str(self.signal_type)
        # Ensure machine-readable location is always populated when a file
        # is known — agents cannot parse file paths from free-text fields.
        if self.file_path is not None and self.start_line is None:
            self.start_line = 1
        # Auto-infer language from file extension when not set explicitly.
        if self.language is None and self.file_path is not None:
            self.language = self._LANG_MAP.get(self.file_path.suffix.lower())
        # Keep explicit field and metadata view in sync for backward compatibility.
        if self.finding_context and "finding_context" not in self.metadata:
            self.metadata["finding_context"] = self.finding_context
        elif self.finding_context is None:
            existing_ctx = self.metadata.get("finding_context")
            if isinstance(existing_ctx, str) and existing_ctx.strip():
                self.finding_context = existing_ctx.strip().lower()


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

    def __post_init__(self) -> None:
        _validate_unit_interval(self.drift_score, "ModuleScore.drift_score")

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
    transition_ratio: float | None


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
    phase_timings: dict[str, float] = field(default_factory=dict)
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
    #: Findings produced by integration adapters (never affect drift_score).
    integration_findings: list[Finding] = field(default_factory=list)

    def __post_init__(self) -> None:
        _validate_unit_interval(self.drift_score, "RepoAnalysis.drift_score")

    @property
    def severity(self) -> Severity:
        return severity_for_score(self.drift_score)

    @property
    def grade(self) -> tuple[str, str]:
        """Letter grade derived from drift score, e.g. ``("B", "Good")``."""
        from drift.scoring.engine import score_to_grade

        return score_to_grade(self.drift_score)

    @property
    def is_degraded(self) -> bool:
        return self.analysis_status == "degraded"

    @property
    def is_fully_reliable(self) -> bool:
        return not self.is_degraded

    def findings_by_severity(self, severity: Severity) -> list[Finding]:
        return [f for f in self.findings if f.severity == severity]

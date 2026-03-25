"""Core data models for Drift analysis."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


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


class PatternCategory(StrEnum):
    ERROR_HANDLING = "error_handling"
    DATA_ACCESS = "data_access"
    API_ENDPOINT = "api_endpoint"
    CACHING = "caching"
    LOGGING = "logging"
    TESTING = "testing"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"


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


@dataclass
class ImportInfo:
    source_file: Path
    imported_module: str
    imported_names: list[str]
    line_number: int
    is_relative: bool = False


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

    signal_type: SignalType
    severity: Severity
    score: float
    title: str
    description: str
    file_path: Path | None = None
    start_line: int | None = None
    end_line: int | None = None
    related_files: list[Path] = field(default_factory=list)
    commit_hash: str | None = None
    ai_attributed: bool = False
    fix: str | None = None
    impact: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModuleScore:
    """Drift score for a single module (directory)."""

    path: Path
    drift_score: float
    signal_scores: dict[SignalType, float] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    file_count: int = 0
    function_count: int = 0
    ai_ratio: float = 0.0

    @property
    def severity(self) -> Severity:
        return severity_for_score(self.drift_score)


@dataclass
class RepoAnalysis:
    """Complete analysis result for a repository."""

    repo_path: Path
    analyzed_at: datetime.datetime
    drift_score: float
    module_scores: list[ModuleScore] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    pattern_catalog: dict[PatternCategory, list[PatternInstance]] = field(default_factory=dict)
    total_files: int = 0
    total_functions: int = 0
    ai_attributed_ratio: float = 0.0
    analysis_duration_seconds: float = 0.0
    commits: list[CommitInfo] = field(default_factory=list)
    file_histories: dict[str, FileHistory] = field(default_factory=dict)
    suppressed_count: int = 0

    @property
    def severity(self) -> Severity:
        return severity_for_score(self.drift_score)

    def findings_by_severity(self, severity: Severity) -> list[Finding]:
        return [f for f in self.findings if f.severity == severity]

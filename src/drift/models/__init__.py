"""Core data models for Drift analysis.

This package re-exports every public symbol that was previously available
in the monolithic ``drift.models`` module.  All existing ``from drift.models
import X`` statements continue to work without modification.
"""

from drift.models._agent import AgentTask as AgentTask
from drift.models._agent import ConsolidationGroup as ConsolidationGroup
from drift.models._context import NegativeContext as NegativeContext
from drift.models._enums import (
    OUTPUT_SCHEMA_VERSION as OUTPUT_SCHEMA_VERSION,
)
from drift.models._enums import (
    AnalysisStatus as AnalysisStatus,
)
from drift.models._enums import (
    AutomationFit as AutomationFit,
)
from drift.models._enums import (
    ChangeScope as ChangeScope,
)
from drift.models._enums import (
    FindingStatus as FindingStatus,
)
from drift.models._enums import (
    NegativeContextCategory as NegativeContextCategory,
)
from drift.models._enums import (
    NegativeContextScope as NegativeContextScope,
)
from drift.models._enums import (
    PatternCategory as PatternCategory,
)
from drift.models._enums import (
    RegressionPattern as RegressionPattern,
)
from drift.models._enums import (
    RegressionReasonCode as RegressionReasonCode,
)
from drift.models._enums import (
    RepairLevel as RepairLevel,
)
from drift.models._enums import (
    RepairMaturity as RepairMaturity,
)
from drift.models._enums import (
    ReviewRisk as ReviewRisk,
)
from drift.models._enums import (
    Severity as Severity,
)
from drift.models._enums import (
    SignalType as SignalType,
)
from drift.models._enums import (
    TaskComplexity as TaskComplexity,
)
from drift.models._enums import (
    TrendDirection as TrendDirection,
)
from drift.models._enums import (
    VerificationStrength as VerificationStrength,
)
from drift.models._enums import (
    severity_for_score as severity_for_score,
)
from drift.models._findings import (
    AnalyzerWarning as AnalyzerWarning,
)
from drift.models._findings import (
    Finding as Finding,
)
from drift.models._findings import (
    LogicalLocation as LogicalLocation,
)
from drift.models._findings import (
    ModuleScore as ModuleScore,
)
from drift.models._findings import (
    RepoAnalysis as RepoAnalysis,
)
from drift.models._findings import (
    TrendContext as TrendContext,
)
from drift.models._git import (
    Attribution as Attribution,
)
from drift.models._git import (
    BlameLine as BlameLine,
)
from drift.models._git import (
    CommitInfo as CommitInfo,
)
from drift.models._git import (
    FileHistory as FileHistory,
)
from drift.models._parse import (
    ClassInfo as ClassInfo,
)
from drift.models._parse import (
    FileInfo as FileInfo,
)
from drift.models._parse import (
    FunctionInfo as FunctionInfo,
)
from drift.models._parse import (
    ImportInfo as ImportInfo,
)
from drift.models._parse import (
    ParseResult as ParseResult,
)
from drift.models._parse import (
    PatternInstance as PatternInstance,
)

__all__ = [
    # Enums & constants
    "OUTPUT_SCHEMA_VERSION",
    "Severity",
    "FindingStatus",
    "TrendDirection",
    "AnalysisStatus",
    "SignalType",
    "RegressionReasonCode",
    "RegressionPattern",
    "RepairLevel",
    "PatternCategory",
    "NegativeContextCategory",
    "NegativeContextScope",
    "TaskComplexity",
    "AutomationFit",
    "ReviewRisk",
    "ChangeScope",
    "VerificationStrength",
    "RepairMaturity",
    "severity_for_score",
    # Parse / ingestion
    "FileInfo",
    "FunctionInfo",
    "ClassInfo",
    "ImportInfo",
    "PatternInstance",
    "ParseResult",
    # Git
    "CommitInfo",
    "FileHistory",
    "BlameLine",
    "Attribution",
    # Findings & analysis
    "LogicalLocation",
    "Finding",
    "AnalyzerWarning",
    "ModuleScore",
    "TrendContext",
    "RepoAnalysis",
    # Agent
    "AgentTask",
    "ConsolidationGroup",
    "NegativeContext",
]

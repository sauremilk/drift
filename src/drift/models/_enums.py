"""Enumerations, constants, and small helper types for Drift models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# ---------------------------------------------------------------------------
# Output schema version (ADR-042)
# ---------------------------------------------------------------------------
# Shared across CLI JSON output and API responses.
# Major: incompatible field removals/renames.  Minor: additive new fields.
OUTPUT_SCHEMA_VERSION = "2.1"

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


class TrendDirection(StrEnum):
    IMPROVING = "improving"
    STABLE = "stable"
    DEGRADING = "degrading"
    BASELINE = "baseline"


class AnalysisStatus(StrEnum):
    COMPLETE = "complete"
    DEGRADED = "degraded"


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


class RegressionReasonCode(StrEnum):
    """Reason why a particular (signal, edit_kind) combination caused a regression.

    Used in :class:`RegressionPattern` to give agents a closed-set explanation
    of what went wrong — no free text, deterministically actionable.
    """

    COSMETIC_ONLY = "cosmetic_only"
    INCOMPLETE_BATCH = "incomplete_batch"
    SIDE_EFFECT_VOLATILITY = "side_effect_volatility"
    RESIDUAL_FINDINGS = "residual_findings"
    WRONG_SCOPE = "wrong_scope"
    SIGNALING_LAG = "signaling_lag"


@dataclass
class RegressionPattern:
    """A (signal, edit_kind, context_feature) combination that historically caused regressions.

    Agents consume these to avoid repeating known failure modes when applying repairs.
    Derived deterministically from outcome logs — no LLM involved.
    """

    edit_kind: str  # e.g. "rename_symbol" — closed set of fix_intent.EDIT_KIND_* values
    context_feature: str  # descriptive qualifier, e.g. "cross_file", "test", "batch_incomplete"
    reason_code: RegressionReasonCode


class RepairLevel(StrEnum):
    """Repair-coverage maturity level for a signal.

    Ordered from least to most capable:

    * ``diagnosis`` – Finding description only, no actionable repair hints.
    * ``plannable`` – Structured recommendation with effort/impact,
      but no concrete code examples.
    * ``example_based`` – Exemplary fix snippets or code-level suggestions.
    * ``verifiable`` – Repair **plus** machine-executable verification plan
      (verify_plan / success_criteria evaluable by agent).
    """

    DIAGNOSIS = "diagnosis"
    PLANNABLE = "plannable"
    EXAMPLE_BASED = "example_based"
    VERIFIABLE = "verifiable"


class TaskComplexity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AutomationFit(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ChangeScope(StrEnum):
    LOCAL = "local"
    MODULE = "module"
    CROSS_MODULE = "cross-module"


class VerificationStrength(StrEnum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


class RepairMaturity(StrEnum):
    VERIFIED = "verified"
    EXPERIMENTAL = "experimental"
    INDIRECT_ONLY = "indirect-only"


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

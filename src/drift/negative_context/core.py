"""Negative-context core: registry, signal-category mapping, shared helpers."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable

from drift.models import (
    Finding,
    NegativeContext,
    NegativeContextCategory,
    NegativeContextScope,
    Severity,
    SignalType,
)

__all__ = [
    "GeneratorFn",
    "_FALLBACK_ONLY_SIGNALS",
    "_GENERATORS",
    "_SEVERITY_SCORE",
    "_SIGNAL_CATEGORY",
    "_affected",
    "_neg_id",
    "_policy_covered_signal_types",
    "_policy_uncovered_registered_signal_ids",
    "_policy_uncovered_signal_types",
    "_register",
    "_sanitize",
    "_scope_from_finding",
]

# ---------------------------------------------------------------------------
# Sanitization helper
# ---------------------------------------------------------------------------

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def _sanitize(value: str, max_len: int = 200) -> str:
    """Strip control characters and truncate metadata strings."""
    cleaned = _CONTROL_RE.sub("", value)
    return cleaned[:max_len]


# ---------------------------------------------------------------------------
# Signal → Category mapping
# ---------------------------------------------------------------------------

_SIGNAL_CATEGORY: dict[str, NegativeContextCategory] = {
    SignalType.PATTERN_FRAGMENTATION: NegativeContextCategory.ARCHITECTURE,
    SignalType.ARCHITECTURE_VIOLATION: NegativeContextCategory.ARCHITECTURE,
    SignalType.MUTANT_DUPLICATE: NegativeContextCategory.ARCHITECTURE,
    SignalType.EXPLAINABILITY_DEFICIT: NegativeContextCategory.COMPLEXITY,
    SignalType.TEMPORAL_VOLATILITY: NegativeContextCategory.ARCHITECTURE,
    SignalType.SYSTEM_MISALIGNMENT: NegativeContextCategory.ARCHITECTURE,
    SignalType.DOC_IMPL_DRIFT: NegativeContextCategory.COMPLETENESS,
    SignalType.BROAD_EXCEPTION_MONOCULTURE: NegativeContextCategory.ERROR_HANDLING,
    SignalType.TEST_POLARITY_DEFICIT: NegativeContextCategory.TESTING,
    SignalType.GUARD_CLAUSE_DEFICIT: NegativeContextCategory.COMPLEXITY,
    SignalType.NAMING_CONTRACT_VIOLATION: NegativeContextCategory.NAMING,
    SignalType.BYPASS_ACCUMULATION: NegativeContextCategory.COMPLETENESS,
    SignalType.EXCEPTION_CONTRACT_DRIFT: NegativeContextCategory.ERROR_HANDLING,
    SignalType.COHESION_DEFICIT: NegativeContextCategory.ARCHITECTURE,
    SignalType.CO_CHANGE_COUPLING: NegativeContextCategory.ARCHITECTURE,
    # Security signals
    SignalType.HARDCODED_SECRET: NegativeContextCategory.SECURITY,
    SignalType.MISSING_AUTHORIZATION: NegativeContextCategory.SECURITY,
    SignalType.INSECURE_DEFAULT: NegativeContextCategory.SECURITY,
    # Additional signals
    SignalType.DEAD_CODE_ACCUMULATION: NegativeContextCategory.COMPLETENESS,
    SignalType.CIRCULAR_IMPORT: NegativeContextCategory.ARCHITECTURE,
    SignalType.FAN_OUT_EXPLOSION: NegativeContextCategory.ARCHITECTURE,
    SignalType.TS_ARCHITECTURE: NegativeContextCategory.ARCHITECTURE,
    SignalType.COGNITIVE_COMPLEXITY: NegativeContextCategory.COMPLEXITY,
    SignalType.PHANTOM_REFERENCE: NegativeContextCategory.COMPLETENESS,
}


# ---------------------------------------------------------------------------
# Generator registry
# ---------------------------------------------------------------------------

GeneratorFn = Callable[[Finding], list[NegativeContext]]
_GENERATORS: dict[str, GeneratorFn] = {}

# Signals that intentionally have no dedicated generator (fallback only)
_FALLBACK_ONLY_SIGNALS: frozenset[str] = frozenset(
    {
        SignalType.TYPE_SAFETY_BYPASS,
    }
)


def _policy_covered_signal_types() -> frozenset[str]:
    """Signal types with a dedicated generator OR explicit fallback-only."""
    return frozenset(_GENERATORS.keys()) | _FALLBACK_ONLY_SIGNALS


def _policy_uncovered_signal_types() -> frozenset[str]:
    """Signal types in the category map but without a generator or policy."""
    return frozenset(_SIGNAL_CATEGORY.keys()) - _policy_covered_signal_types()


def _policy_uncovered_registered_signal_ids() -> frozenset[str]:
    """Signal IDs in signal_registry without generator or explicit fallback policy."""
    from drift.signal_registry import get_all_meta

    registered_signal_ids = {meta.signal_id for meta in get_all_meta()}
    return frozenset(registered_signal_ids) - _policy_covered_signal_types()


def _register(signal_type: str) -> Callable[[GeneratorFn], GeneratorFn]:
    """Decorator: register a generator for *signal_type*."""

    def decorator(fn: GeneratorFn) -> GeneratorFn:
        _GENERATORS[signal_type] = fn
        return fn

    return decorator


# ---------------------------------------------------------------------------
# Shared helpers used by generators
# ---------------------------------------------------------------------------


def _neg_id(signal_type: str, finding: Finding) -> str:
    """Generate a deterministic anti-pattern ID."""
    fp = finding.file_path.as_posix() if finding.file_path else ""
    blob = f"neg:{signal_type}:{fp}:{finding.title}"
    short_hash = hashlib.sha256(blob.encode()).hexdigest()[:10]
    return f"neg-{signal_type[:3]}-{short_hash}"


def _affected(finding: Finding) -> list[str]:
    """Extract affected file paths from a finding."""
    files: list[str] = []
    if finding.file_path:
        files.append(finding.file_path.as_posix())
    for extra in finding.metadata.get("affected_files", []):
        if isinstance(extra, str) and extra not in files:
            files.append(extra)
    return files


def _scope_from_finding(finding: Finding) -> NegativeContextScope:
    """Infer the NegativeContextScope from a finding."""
    if finding.file_path:
        return NegativeContextScope.FILE
    return NegativeContextScope.MODULE


# ---------------------------------------------------------------------------
# Severity score for prioritization
# ---------------------------------------------------------------------------

_SEVERITY_SCORE: dict[Severity, int] = {
    Severity.CRITICAL: 5,
    Severity.HIGH: 4,
    Severity.MEDIUM: 3,
    Severity.LOW: 2,
    Severity.INFO: 1,
}

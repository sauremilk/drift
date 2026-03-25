"""Signal 8: Broad Exception Monoculture (BEM).

Detects modules where exception handling is uniformly broad and
swallowing — a structural proxy for "consistent wrongness" where the
codebase does error handling the same way everywhere, but that way is
overly permissive (bare except, Exception, BaseException with only
pass/log/print actions).

Epistemics: Cannot detect WHAT the error model gets wrong, but CAN
detect the structural conditions (uniform non-differentiation) under
which error-handling monoculture thrives.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    ParseResult,
    PatternCategory,
    SignalType,
    severity_for_score,
)
from drift.signals.base import BaseSignal, register_signal

# Exception types considered "overly broad"
_BROAD_TYPES: frozenset[str] = frozenset({"bare", "Exception", "BaseException"})

# Actions that indicate a handler swallows the error without meaningful recovery
_SWALLOWING_ACTIONS: frozenset[str] = frozenset({"pass", "log", "print"})

# Module filenames that intentionally use broad handlers (middleware, error
# boundary layers).  Excluding them avoids false positives on code that is
# *supposed* to catch broadly.
_BOUNDARY_STEMS: frozenset[str] = frozenset({
    "middleware",
    "error_handler",
    "exception_handler",
    "error_boundary",
    "error_middleware",
})


def _is_error_boundary(file_path: Path) -> bool:
    """Return True if *file_path* looks like an intentional error-boundary module."""
    stem = file_path.stem.lower()
    return stem in _BOUNDARY_STEMS


@register_signal
class BroadExceptionMonocultureSignal(BaseSignal):
    """Detect modules with uniformly broad, swallowing exception handling."""

    @property
    def signal_type(self) -> SignalType:
        return SignalType.BROAD_EXCEPTION_MONOCULTURE

    @property
    def name(self) -> str:
        return "Broad Exception Monoculture"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        min_handlers = config.thresholds.bem_min_handlers

        # Collect error-handling patterns grouped by module directory
        module_handlers: dict[Path, list[dict]] = defaultdict(list)
        module_files: dict[Path, set[Path]] = defaultdict(set)

        for pr in parse_results:
            if _is_error_boundary(pr.file_path):
                continue
            for pattern in pr.patterns:
                if pattern.category != PatternCategory.ERROR_HANDLING:
                    continue
                fp = pattern.fingerprint
                handlers = fp.get("handlers", [])
                if not handlers:
                    continue
                module = pattern.file_path.parent
                module_files[module].add(pattern.file_path)
                for h in handlers:
                    module_handlers[module].append(h)

        findings: list[Finding] = []

        for module, handlers in module_handlers.items():
            total = len(handlers)
            if total < min_handlers:
                continue

            broad_count = sum(
                1 for h in handlers if h.get("exception_type", "") in _BROAD_TYPES
            )
            swallowing_count = sum(
                1
                for h in handlers
                if set(h.get("actions", [])).issubset(_SWALLOWING_ACTIONS)
                and h.get("actions")  # empty actions list should not count
            )

            broadness_ratio = broad_count / total
            swallowing_ratio = swallowing_count / total

            if broadness_ratio < 0.80 or swallowing_ratio < 0.60:
                continue

            score = min(1.0, broadness_ratio * swallowing_ratio)
            severity = severity_for_score(score)
            files = sorted(module_files[module])

            findings.append(
                Finding(
                    signal_type=SignalType.BROAD_EXCEPTION_MONOCULTURE,
                    severity=severity,
                    score=score,
                    title=f"Exception-Monokultur: {module}",
                    description=(
                        f"{broad_count}/{total} Handler sind breit "
                        f"({broadness_ratio:.0%}), "
                        f"{swallowing_count}/{total} verschlucken Fehler "
                        f"({swallowing_ratio:.0%}). "
                        f"Uniforme Broad-Catches deuten auf fehlende "
                        f"Fehlerklassen-Differenzierung."
                    ),
                    file_path=files[0] if files else None,
                    related_files=files[1:],
                    fix=(
                        f"Modul {module.name}: Differenziere Exception-Handler "
                        f"nach konkreten Fehlerklassen und ersetze "
                        f"pass/log-only Handler durch spezifische Recovery."
                    ),
                    metadata={
                        "total_handlers": total,
                        "broad_count": broad_count,
                        "swallowing_count": swallowing_count,
                        "broadness_ratio": broadness_ratio,
                        "swallowing_ratio": swallowing_ratio,
                    },
                )
            )

        return findings

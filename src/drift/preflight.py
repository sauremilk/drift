"""Preflight diagnostics for drift analyze.

Performs lightweight checks before the full analysis pipeline runs,
giving users immediate feedback about what will be analyzed, what
will be skipped, and why.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import drift.signals
from drift.ingestion.file_discovery import discover_files
from drift.pipeline import is_git_repo
from drift.signals.base import _SIGNAL_REGISTRY

if TYPE_CHECKING:
    from drift.config import DriftConfig

logger = logging.getLogger("drift")

# Ensure all signal modules are imported so _SIGNAL_REGISTRY is populated.
for _finder, _mod_name, _ispkg in pkgutil.iter_modules(drift.signals.__path__):
    importlib.import_module(f"drift.signals.{_mod_name}")


@dataclass
class SkippedSignal:
    """A signal that will be skipped with an explanation and actionable hint."""

    signal_id: str
    signal_name: str
    reason: str
    hint: str


@dataclass
class PreflightResult:
    """Result of the preflight diagnostics run before analysis."""

    git_available: bool = False
    python_files_found: int = 0
    total_files_found: int = 0
    excluded_patterns: list[str] = field(default_factory=list)
    active_signals: list[str] = field(default_factory=list)
    skipped_signals: list[SkippedSignal] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    can_proceed: bool = True
    abort_reason: str | None = None

    @property
    def skipped_count(self) -> int:
        """Number of signals that will be skipped."""
        return len(self.skipped_signals)

    @property
    def active_count(self) -> int:
        """Number of signals that will run."""
        return len(self.active_signals)

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dictionary."""
        return {
            "git_available": self.git_available,
            "python_files_found": self.python_files_found,
            "total_files_found": self.total_files_found,
            "excluded_patterns": self.excluded_patterns,
            "active_signals": self.active_signals,
            "skipped_signals": [
                {
                    "signal_id": s.signal_id,
                    "signal_name": s.signal_name,
                    "reason": s.reason,
                    "hint": s.hint,
                }
                for s in self.skipped_signals
            ],
            "warnings": self.warnings,
            "can_proceed": self.can_proceed,
            "abort_reason": self.abort_reason,
        }


# Map signal_type values to human-readable abbreviations
_SIGNAL_ABBREVS: dict[str, str] = {
    "pattern_fragmentation": "PFS",
    "architecture_violation": "AVS",
    "mutant_duplicate": "MDS",
    "explainability_deficit": "EDS",
    "doc_impl_drift": "DIA",
    "temporal_volatility": "TVS",
    "system_misalignment": "SMS",
    "broad_exception_monoculture": "BEM",
    "test_polarity_deficit": "TPD",
    "guard_clause_deficit": "GCD",
    "naming_contract_violation": "NBV",
    "bypass_accumulation": "BAT",
    "exception_contract_drift": "ECM",
    "cohesion_deficit": "COD",
    "co_change_coupling": "CCC",
    "circular_import": "CIR",
    "fan_out_explosion": "FOE",
    "dead_code_accumulation": "DCA",
    "cognitive_complexity": "CXS",
    "ts_architecture": "TSA",
    "missing_authorization": "MAZ",
    "insecure_default": "ISD",
    "hardcoded_secret": "HSC",  # pragma: allowlist secret
}


def run_preflight(
    repo_path: Path,
    config: DriftConfig,
    *,
    active_signals: set[str] | None = None,
) -> PreflightResult:
    """Run preflight diagnostics and return a structured result.

    This is a lightweight check that runs before the full analysis
    pipeline. It verifies prerequisites and predicts which signals
    will be available.
    """
    result = PreflightResult()

    # 1. Check git availability
    result.git_available = is_git_repo(repo_path)

    # 2. Collect exclude patterns from config
    result.excluded_patterns = list(config.exclude) if config.exclude else []

    # 3. Discover analysable files
    try:
        files = discover_files(
            repo_path,
            include=config.include,
            exclude=config.exclude,
            max_files=config.thresholds.max_discovery_files,
        )
        result.total_files_found = len(files)
        result.python_files_found = sum(1 for f in files if f.language == "python")
    except Exception as exc:
        logger.warning("Preflight file discovery failed: %s", exc)
        result.warnings.append(f"File discovery failed: {exc}")

    # 4. Check if we can proceed
    if result.total_files_found == 0:
        result.can_proceed = False
        if result.excluded_patterns:
            result.abort_reason = (
                "No analysable files found. Your exclude patterns may be "
                "filtering out all source files. Check your drift.yaml "
                "or the default excludes (tests/, scripts/, venv/, etc.)."
            )
        else:
            result.abort_reason = (
                "No analysable Python files found in this repository. "
                "Drift currently supports Python (.py) files. "
                "Ensure the repository contains Python source code."
            )
        return result

    # 5. Determine which signals are active vs skipped
    git_dependent_signals: list[tuple[str, str]] = []  # (signal_type_value, name)
    non_git_signals: list[tuple[str, str]] = []

    for cls in _SIGNAL_REGISTRY:
        try:
            probe = cls()
        except TypeError:
            # Legacy constructors — try with minimal args
            try:
                probe = cls(repo_path=repo_path)  # type: ignore[call-arg]
            except Exception:
                continue
        sig_type = str(probe.signal_type)
        sig_name = probe.name

        # Apply signal filter
        if active_signals is not None and sig_type.upper() not in active_signals:
            abbrev = _SIGNAL_ABBREVS.get(sig_type, sig_type.upper())
            if abbrev not in active_signals:
                continue

        scope = getattr(cls, "incremental_scope", "cross_file")
        if scope == "git_dependent":
            git_dependent_signals.append((sig_type, sig_name))
        else:
            non_git_signals.append((sig_type, sig_name))

    # Non-git signals are always active (if files exist)
    for sig_type, _sig_name in non_git_signals:
        abbrev = _SIGNAL_ABBREVS.get(sig_type, sig_type.upper())
        result.active_signals.append(abbrev)

    # Git-dependent signals depend on git availability
    for sig_type, sig_name in git_dependent_signals:
        abbrev = _SIGNAL_ABBREVS.get(sig_type, sig_type.upper())
        if result.git_available:
            result.active_signals.append(abbrev)
        else:
            result.skipped_signals.append(
                SkippedSignal(
                    signal_id=abbrev,
                    signal_name=sig_name,
                    reason="No git history available",
                    hint=(
                        "Clone with full history: git clone <url> (avoid --depth 1). "
                        "Or initialize git: git init && git add -A && git commit -m 'init'"
                    ),
                )
            )

    # 6. Additional warnings
    if not result.git_available:
        result.warnings.append(
            "No .git directory found. Git-dependent signals (TVS, SMS, ECM, CCC) "
            "will be skipped. Clone with full history for complete analysis."
        )

    if result.python_files_found == 0 and result.total_files_found > 0:
        result.warnings.append(
            f"Found {result.total_files_found} files but none are Python. "
            "Drift primarily analyses Python source code."
        )

    return result

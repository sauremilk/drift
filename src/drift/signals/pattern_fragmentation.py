"""Signal 1: Pattern Fragmentation Score (PFS).

Detects when the same category of code pattern (e.g. error handling)
has multiple incompatible variants within the same module, indicating
inconsistent approaches — often from different AI generation sessions.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from drift.config import DriftConfig
from drift.models import (
    FileHistory,
    Finding,
    ParseResult,
    PatternCategory,
    PatternInstance,
    Severity,
    SignalType,
)
from drift.signals._utils import is_test_file
from drift.signals.base import BaseSignal, register_signal

_FRAMEWORK_SURFACE_TOKENS: frozenset[str] = frozenset(
    {
        "api",
        "router",
        "routers",
        "route",
        "routes",
        "controller",
        "controllers",
        "endpoint",
        "endpoints",
        "handler",
        "handlers",
        "page",
        "pages",
        "view",
        "views",
        "server",
        "mcp",
        "orchestration",
        "orchestrator",
    },
)


def _normalize_fingerprint(fingerprint: dict[str, Any]) -> dict[str, Any]:
    """Normalize fingerprint to reduce false positives from async/sync equivalence.

    Removes async-specific markers so that ``async def`` and ``def``
    versions of the same pattern are grouped together.
    """
    normalized = dict(fingerprint)
    # Treat async/sync variants as equivalent
    normalized.pop("is_async", None)
    normalized.pop("async", None)
    # Normalize await expressions to regular calls
    if "body" in normalized and isinstance(normalized["body"], str):
        normalized["body"] = normalized["body"].replace("await ", "").replace("async ", "")
    return normalized


def _variant_key(fingerprint: dict[str, Any]) -> str:
    """Create a hashable key from a pattern fingerprint for grouping."""
    normalized = _normalize_fingerprint(fingerprint)
    return json.dumps(normalized, sort_keys=True, default=str)


def _group_by_module(
    patterns: list[PatternInstance],
) -> dict[Path, list[PatternInstance]]:
    """Group patterns by their parent directory (module)."""
    groups: dict[Path, list[PatternInstance]] = defaultdict(list)
    for p in patterns:
        module = p.file_path.parent
        groups[module].append(p)
    return groups


def _count_variants(
    patterns: list[PatternInstance],
) -> dict[str, list[PatternInstance]]:
    """Group patterns by their fingerprint variant."""
    variants: dict[str, list[PatternInstance]] = defaultdict(list)
    for p in patterns:
        key = _variant_key(p.fingerprint)
        variants[key].append(p)
    return variants


def _canonical_variant(variants: dict[str, list[PatternInstance]]) -> str:
    """Identify the canonical (most-used) variant."""
    return max(variants, key=lambda k: len(variants[k]))


def _instance_ref(pattern: PatternInstance) -> str:
    """Build a stable location reference for action-oriented guidance."""
    return f"{pattern.file_path.as_posix()}:{pattern.start_line}"


def _tokenize_path(value: str) -> set[str]:
    """Tokenize a path-like string into lowercase alphanumeric chunks."""
    return {tok for tok in re.split(r"[^a-z0-9]+", value.lower()) if tok}


def _framework_surface_hints(
    module_path: Path,
    module_patterns: list[PatternInstance],
    endpoint_modules: set[Path],
) -> list[str]:
    """Return heuristic hints that a module is framework-facing surface code."""
    hints: list[str] = []

    if module_path in endpoint_modules:
        hints.append("api-endpoint-pattern")

    module_tokens = _tokenize_path(module_path.as_posix())
    if module_tokens & _FRAMEWORK_SURFACE_TOKENS:
        hints.append("module-path-token")

    file_tokens: set[str] = set()
    for pattern in module_patterns:
        file_tokens |= _tokenize_path(pattern.file_path.stem)
    if file_tokens & _FRAMEWORK_SURFACE_TOKENS:
        hints.append("filename-token")

    return hints


def _extract_canonical_snippet(file_path: str, start_line: int, max_lines: int = 8) -> str:
    """Read source lines around start_line for canonical pattern display (ADR-049)."""
    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()
        snippet_lines = lines[start_line - 1 : start_line - 1 + max_lines]
        return "".join(snippet_lines).rstrip()
    except (OSError, IndexError):
        return ""


@register_signal
class PatternFragmentationSignal(BaseSignal):
    """Detect multiple incompatible pattern variants within architectural modules."""

    incremental_scope = "file_local"

    @property
    def signal_type(self) -> SignalType:
        return SignalType.PATTERN_FRAGMENTATION

    @property
    def name(self) -> str:
        return "Pattern Fragmentation"

    def analyze(
        self,
        parse_results: list[ParseResult],
        file_histories: dict[str, FileHistory],
        config: DriftConfig,
    ) -> list[Finding]:
        # Gather all patterns from all files
        all_patterns: dict[PatternCategory, list[PatternInstance]] = defaultdict(list)
        for pr in parse_results:
            if is_test_file(pr.file_path):
                continue
            for pattern in pr.patterns:
                all_patterns[pattern.category].append(pattern)

        findings: list[Finding] = []
        endpoint_modules = {
            p.file_path.parent
            for p in all_patterns.get(PatternCategory.API_ENDPOINT, [])
        }

        for category, patterns in all_patterns.items():
            # Analyze per-module fragmentation
            module_groups = _group_by_module(patterns)

            for module_path, module_patterns in module_groups.items():
                if len(module_patterns) < 2:
                    continue

                variants = _count_variants(module_patterns)
                num_variants = len(variants)

                if num_variants <= 1:
                    continue

                canonical = _canonical_variant(variants)
                canonical_count = len(variants[canonical])
                total = len(module_patterns)
                non_canonical = [p for key, ps in variants.items() if key != canonical for p in ps]

                frag_score = 1 - (1 / num_variants)

                # Boost score when many non-canonical instances exist.
                # A module with 20 error-handling instances and 3 variants is
                # worse than one with 3 instances and 3 variants — the spread
                # of deviations across the codebase amplifies maintenance cost.
                non_canonical_count = total - canonical_count
                if non_canonical_count > 2:
                    spread_factor = min(1.5, 1.0 + (non_canonical_count - 2) * 0.04)
                    frag_score = min(1.0, frag_score * spread_factor)

                framework_hints: list[str] = []
                if category is PatternCategory.ERROR_HANDLING:
                    framework_hints = _framework_surface_hints(
                        module_path=module_path,
                        module_patterns=module_patterns,
                        endpoint_modules=endpoint_modules,
                    )
                    if framework_hints:
                        # Framework boundary layers often require heterogenous
                        # error behavior and should not default to HIGH urgency.
                        frag_score *= 0.65

                # Build description
                desc_parts = [
                    f"{num_variants} {category.value} variants in {module_path.as_posix()}/ "
                    f"({canonical_count}/{total} use canonical pattern).",
                ]
                if framework_hints:
                    desc_parts.append(
                        "  - Framework-facing module detected; severity was "
                        "context-calibrated for endpoint/orchestration diversity."
                    )
                for p in non_canonical[:3]:
                    desc_parts.append(
                        f"  - {_instance_ref(p)} ({p.function_name})"
                    )

                severity = Severity.INFO
                if frag_score >= 0.7:
                    severity = Severity.HIGH
                elif frag_score >= 0.5:
                    severity = Severity.MEDIUM
                elif frag_score >= 0.3:
                    severity = Severity.LOW

                if framework_hints and severity is Severity.HIGH:
                    severity = Severity.MEDIUM

                # Canonical-ratio downgrade: weak patterns (very few canonical instances)
                # should not fire with the same urgency as dominant ones (ADR-049).
                canonical_ratio = canonical_count / total if total > 0 else 1.0
                if canonical_ratio < 0.10:
                    if severity is Severity.HIGH:
                        severity = Severity.MEDIUM
                    elif severity is Severity.MEDIUM:
                        severity = Severity.LOW
                elif canonical_ratio < 0.15 and severity is Severity.HIGH:
                    severity = Severity.MEDIUM

                nc_count = len(non_canonical)
                canonical_examples = sorted(
                    variants[canonical],
                    key=lambda p: (p.file_path.as_posix(), p.start_line, p.function_name),
                )
                canonical_exemplar = canonical_examples[0]
                deviation_examples = sorted(
                    non_canonical,
                    key=lambda p: (p.file_path.as_posix(), p.start_line, p.function_name),
                )
                deviation_refs = [
                    f"{_instance_ref(p)} ({p.function_name})"
                    for p in deviation_examples[:3]
                ]
                if nc_count > 3:
                    deviation_refs.append(f"+{nc_count - 3} more")

                canonical_snippet = _extract_canonical_snippet(
                    canonical_exemplar.file_path.as_posix(),
                    canonical_exemplar.start_line,
                )

                fix = (
                    f"Consolidate to the dominant pattern ({canonical_count}x, "
                    f"exemplar: {_instance_ref(canonical_exemplar)}). "
                    f"Deviations: {', '.join(deviation_refs)}."
                )

                findings.append(
                    Finding(
                        signal_type=self.signal_type,
                        severity=severity,
                        score=frag_score,
                        title=(
                            f"{category.value}: {num_variants} variants"
                            f" in {module_path.as_posix()}/"
                        ),
                        description="\n".join(desc_parts),
                        file_path=module_path,
                        related_files=[p.file_path for p in non_canonical],
                        fix=fix,
                        metadata={
                            "category": category.value,
                            "num_variants": num_variants,
                            "variant_count": num_variants,
                            "canonical_count": canonical_count,
                            "canonical_variant": canonical[:60],
                            "canonical_exemplar": _instance_ref(canonical_exemplar),
                            "canonical_snippet": canonical_snippet[:400],
                            "canonical_ratio": round(canonical_ratio, 3),
                            "module": module_path.as_posix(),
                            "total_instances": total,
                            "framework_context_dampened": bool(framework_hints),
                            "framework_context_hints": framework_hints,
                            "deliberate_pattern_risk": (
                                "May reflect architecture transition or deliberate variation. "
                                "Review whether variants serve distinct purposes."
                            ),
                        },
                    )
                )

        return findings

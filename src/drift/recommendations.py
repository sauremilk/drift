"""Rule-based actionable recommendations for drift findings.

Generates concrete suggestions for how to fix detected issues —
no LLM needed, pure pattern matching on findings and metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from drift.models import Finding, SignalType


@dataclass
class Recommendation:
    """A concrete, actionable suggestion to reduce drift."""

    title: str
    description: str
    effort: str  # "low", "medium", "high"
    impact: str  # "low", "medium", "high"
    file_path: Path | None = None
    related_findings: list[Finding] | None = None


def _recommend_pattern_fragmentation(finding: Finding) -> Recommendation | None:
    """Suggest merging fragmented pattern variants."""
    meta = finding.metadata
    variants = meta.get("variant_count", 0)
    canonical = meta.get("canonical_variant", "")
    module = meta.get("module", "")

    if variants < 2:
        return None

    files = finding.related_files
    file_list = ", ".join(f.as_posix() for f in files[:3]) if files else "?"
    extra = f" (+{len(files) - 3} more)" if files and len(files) > 3 else ""

    return Recommendation(
        title=f"Consolidate {variants} pattern variants in {module or '?'}",
        description=(
            f"Found {variants} variants of the same pattern. "
            f"Adopt the canonical variant '{canonical}' across: "
            f"{file_list}{extra}. "
            f"Extract a shared helper function and replace inline "
            f"implementations."
        ),
        effort="medium",
        impact="high",
        file_path=finding.file_path,
        related_findings=[finding],
    )


def _recommend_architecture_violation(finding: Finding) -> Recommendation | None:
    """Suggest fixing layer boundary violations."""
    meta = finding.metadata

    if "circular" in finding.title.lower():
        cycle = meta.get("cycle", [])
        cycle_str = " → ".join(str(c) for c in cycle[:5])
        return Recommendation(
            title="Break circular dependency",
            description=(
                f"Circular import detected: {cycle_str}. "
                f"Extract shared interfaces into a separate module "
                f"that both sides can import, or use dependency "
                f"injection to invert the dependency direction."
            ),
            effort="medium",
            impact="high",
            file_path=finding.file_path,
            related_findings=[finding],
        )

    if "upward" in finding.title.lower() or "layer" in finding.title.lower():
        return Recommendation(
            title="Fix upward layer import",
            description=(
                f"{finding.description} "
                f"Move the shared code to a lower-level module, "
                f"or introduce an interface/protocol that the lower "
                f"layer defines and the upper layer implements."
            ),
            effort="medium",
            impact="high",
            file_path=finding.file_path,
            related_findings=[finding],
        )

    return None


def _recommend_mutant_duplicate(finding: Finding) -> Recommendation | None:
    """Suggest merging near-duplicate functions."""
    meta = finding.metadata
    func_a = meta.get("function_a", "?")
    func_b = meta.get("function_b", "?")
    similarity = meta.get("similarity", 0.0)
    file_a = meta.get("file_a", "")
    file_b = meta.get("file_b", "")

    if file_a == file_b:
        location = f"in {file_a}"
        action = (
            f"These two functions are {similarity:.0%} similar. "
            f"Merge them into one, parameterizing the differences. "
            f"If the differences are in data, pass them as arguments. "
            f"If in behavior, use a strategy parameter or callback."
        )
    else:
        location = f"across {file_a} and {file_b}"
        action = (
            f"These functions are {similarity:.0%} similar but in "
            f"different files. Extract the common logic into a shared "
            f"utility module, then have both call the shared version."
        )

    return Recommendation(
        title=f"Merge '{func_a}' and '{func_b}' ({location})",
        description=action,
        effort="low",
        impact="high",
        file_path=finding.file_path,
        related_findings=[finding],
    )


def _recommend_explainability_deficit(finding: Finding) -> Recommendation | None:
    """Suggest adding documentation to complex undocumented functions."""
    meta = finding.metadata
    func_name = meta.get("function_name", "?")
    complexity = meta.get("complexity", 0)
    has_docstring = meta.get("has_docstring", True)
    has_types = meta.get("has_return_type", True)

    suggestions: list[str] = []
    if not has_docstring:
        suggestions.append(
            f"Add a docstring explaining what '{func_name}' does, its parameters, and return value"
        )
    if not has_types:
        suggestions.append("Add return type annotation")
    if complexity > 10:
        suggestions.append(
            f"Consider splitting this function (complexity: {complexity}) "
            f"into smaller, well-named sub-functions"
        )

    if not suggestions:
        return None

    return Recommendation(
        title=f"Document '{func_name}'",
        description=". ".join(suggestions) + ".",
        effort="low",
        impact="medium",
        file_path=finding.file_path,
        related_findings=[finding],
    )


def _recommend_temporal_volatility(finding: Finding) -> Recommendation | None:
    """Suggest stabilizing volatile modules."""
    meta = finding.metadata
    ai_ratio = meta.get("ai_ratio", 0.0)
    change_freq = meta.get("change_frequency_30d", 0.0)

    suggestions: list[str] = []
    if ai_ratio > 0.5:
        suggestions.append(
            "This file has a high AI-commit ratio — review AI-generated "
            "changes more carefully and ensure they follow project conventions"
        )
    if change_freq > 3.0:
        suggestions.append(
            f"High churn ({change_freq:.1f} changes/week). "
            f"Consider stabilizing the interface before adding features"
        )
    suggestions.append(
        "Add integration tests to catch regressions early and reduce the fix-commit cycle"
    )

    return Recommendation(
        title=f"Stabilize {finding.file_path}",
        description=". ".join(suggestions) + ".",
        effort="medium",
        impact="medium",
        file_path=finding.file_path,
        related_findings=[finding],
    )


def _recommend_system_misalignment(finding: Finding) -> Recommendation | None:
    """Suggest addressing novel dependencies."""
    meta = finding.metadata
    novel_deps = meta.get("novel_imports", [])
    if not novel_deps:
        novel_deps = meta.get("novel_dependencies", [])

    dep_list = ", ".join(str(d) for d in novel_deps[:5])

    return Recommendation(
        title=f"Review novel dependencies in {finding.file_path}",
        description=(
            f"Recently introduced dependencies ({dep_list}) diverge "
            f"from this module's established import patterns. "
            f"Verify these are intentional. If not, move the "
            f"dependent code to a more appropriate module."
        ),
        effort="low",
        impact="medium",
        file_path=finding.file_path,
        related_findings=[finding],
    )


def _recommend_cohesion_deficit(finding: Finding) -> Recommendation | None:
    """Suggest splitting unrelated responsibilities into cohesive modules."""
    meta = finding.metadata
    unit_count = meta.get("unit_count", 0)
    isolated_count = meta.get("isolated_count", 0)
    isolated_units = meta.get("isolated_units", [])

    if unit_count < 4 or isolated_count == 0:
        return None

    preview = ", ".join(str(name) for name in isolated_units[:4])
    if len(isolated_units) > 4:
        preview += f" (+{len(isolated_units) - 4} more)"

    return Recommendation(
        title=f"Split low-cohesion module ({isolated_count}/{unit_count} isolated units)",
        description=(
            "This file mixes unrelated responsibilities. "
            f"Start by extracting isolated units ({preview}) into focused modules, "
            "group by stable domain vocabulary, and keep one clear responsibility per file."
        ),
        effort="medium",
        impact="high",
        file_path=finding.file_path,
        related_findings=[finding],
    )


def _recommend_co_change_coupling(finding: Finding) -> Recommendation | None:
    """Suggest making hidden co-change dependencies explicit or decoupled."""
    meta = finding.metadata
    file_a = str(meta.get("file_a") or (finding.file_path.as_posix() if finding.file_path else "?"))

    file_b = "?"
    if "file_b" in meta:
        file_b = str(meta.get("file_b"))
    elif finding.related_files:
        file_b = finding.related_files[0].as_posix()

    confidence = float(meta.get("confidence", 0.0) or 0.0)
    weight = float(meta.get("co_change_weight", 0.0) or 0.0)

    return Recommendation(
        title=f"Make hidden coupling explicit: {Path(file_a).name} <-> {Path(file_b).name}",
        description=(
            f"{Path(file_a).name} and {Path(file_b).name} co-change with "
            f"confidence {confidence:.0%} (weighted support {weight:.2f}) "
            "without an explicit import edge. "
            "Choose one direction of dependency, extract shared behavior into a "
            "small shared module or interface, and add a regression test that "
            "fails when one side changes without the required counterpart update."
        ),
        effort="medium",
        impact="high",
        file_path=finding.file_path,
        related_findings=[finding],
    )


# Dispatcher: signal type → recommendation generator
_RECOMMENDERS = {
    SignalType.PATTERN_FRAGMENTATION: _recommend_pattern_fragmentation,
    SignalType.ARCHITECTURE_VIOLATION: _recommend_architecture_violation,
    SignalType.MUTANT_DUPLICATE: _recommend_mutant_duplicate,
    SignalType.EXPLAINABILITY_DEFICIT: _recommend_explainability_deficit,
    SignalType.TEMPORAL_VOLATILITY: _recommend_temporal_volatility,
    SignalType.SYSTEM_MISALIGNMENT: _recommend_system_misalignment,
    SignalType.COHESION_DEFICIT: _recommend_cohesion_deficit,
    SignalType.CO_CHANGE_COUPLING: _recommend_co_change_coupling,
}


def generate_recommendation(finding: Finding) -> Recommendation | None:
    """Generate one actionable recommendation for a single finding."""
    recommender = _RECOMMENDERS.get(finding.signal_type)
    if recommender is None:
        return None
    return recommender(finding)


def generate_recommendations(
    findings: list[Finding],
    max_recommendations: int = 10,
) -> list[Recommendation]:
    """Generate actionable recommendations from analysis findings.

    Returns at most *max_recommendations*, prioritized by impact then effort.
    """
    recs: list[Recommendation] = []

    # Sort findings by score descending — most impactful first
    sorted_findings = sorted(findings, key=lambda f: f.score, reverse=True)

    seen_titles: set[str] = set()
    for finding in sorted_findings:
        rec = generate_recommendation(finding)
        if rec is None:
            continue

        # Deduplicate by title
        if rec.title in seen_titles:
            continue
        seen_titles.add(rec.title)

        recs.append(rec)
        if len(recs) >= max_recommendations:
            break

    # Sort: high impact first, then low effort first
    impact_order = {"high": 0, "medium": 1, "low": 2}
    effort_order = {"low": 0, "medium": 1, "high": 2}
    recs.sort(key=lambda r: (impact_order.get(r.impact, 9), effort_order.get(r.effort, 9)))

    return recs

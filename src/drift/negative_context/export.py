"""Render negative context items for agent consumption.

Supports three output formats:
- ``instructions``: compatible with ``.instructions.md`` / copilot-instructions
- ``prompt``: compact summary for system prompt usage
- ``raw``: machine-readable JSON payload for automation pipelines
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from drift.models import (
    NegativeContext,
    NegativeContextCategory,
    Severity,
)
from drift.response_shaping import build_drift_score_scope

# ---------------------------------------------------------------------------
# Category labels for section headings
# ---------------------------------------------------------------------------

_CATEGORY_HEADING: dict[NegativeContextCategory, str] = {
    NegativeContextCategory.SECURITY: "Security Anti-Patterns",
    NegativeContextCategory.ERROR_HANDLING: "Error Handling Anti-Patterns",
    NegativeContextCategory.ARCHITECTURE: "Architecture Anti-Patterns",
    NegativeContextCategory.TESTING: "Testing Anti-Patterns",
    NegativeContextCategory.NAMING: "Naming Anti-Patterns",
    NegativeContextCategory.COMPLEXITY: "Complexity Anti-Patterns",
    NegativeContextCategory.COMPLETENESS: "Completeness Anti-Patterns",
}

_SEVERITY_ICON: dict[Severity, str] = {
    Severity.CRITICAL: "[!!]",
    Severity.HIGH: "[!]",
    Severity.MEDIUM: "[*]",
    Severity.LOW: "[-]",
    Severity.INFO: "[.]",
}

# Merge markers for safe update of existing files
MARKER_BEGIN = (
    "<!-- drift:negative-context:begin -- auto-generated anti-pattern constraints from drift -->"
)
MARKER_END = "<!-- drift:negative-context:end -->"


@dataclass
class _DeduplicatedContext:
    """Aggregated negative-context group with variant traceability."""

    item: NegativeContext
    occurrences: int
    forbidden_variants: list[str]


def _dedup_key(nc: NegativeContext) -> tuple[str, str, str, str, str]:
    """Return grouping key for remediation-equivalent anti-pattern rules."""
    return (
        nc.category.value,
        nc.source_signal,
        nc.severity.value,
        nc.canonical_alternative or "",
        nc.rationale or "",
    )


def _deduplicate_items(items: list[NegativeContext]) -> list[_DeduplicatedContext]:
    """Merge duplicate rule entries while preserving first-seen order.

    Rules are considered duplicates when category, signal, severity, and
    remediation rationale match. Affected file lists are merged while retaining
    distinct forbidden-pattern variants for traceability.
    """
    grouped: dict[tuple[str, str, str, str, str], _DeduplicatedContext] = {}
    order: list[tuple[str, str, str, str, str]] = []

    for item in items:
        key = _dedup_key(item)
        variant = item.forbidden_pattern or ""
        if key not in grouped:
            grouped[key] = _DeduplicatedContext(
                item=replace(item, affected_files=list(item.affected_files)),
                occurrences=1,
                forbidden_variants=[variant] if variant else [],
            )
            order.append(key)
            continue

        current = grouped[key]
        merged_files = list(dict.fromkeys([*current.item.affected_files, *item.affected_files]))
        forbidden_variants = list(current.forbidden_variants)
        if variant and variant not in forbidden_variants:
            forbidden_variants.append(variant)

        grouped[key] = _DeduplicatedContext(
            item=replace(current.item, affected_files=merged_files),
            occurrences=current.occurrences + 1,
            forbidden_variants=forbidden_variants,
        )

    return [grouped[key] for key in order]


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _render_item(group: _DeduplicatedContext) -> str:
    """Render a single NegativeContext as a Markdown list entry."""
    nc = group.item
    icon = _SEVERITY_ICON.get(nc.severity, "")
    lines: list[str] = []
    occurrence_note = f" ({group.occurrences} occurrences)" if group.occurrences > 1 else ""

    lines.append(
        f"- {icon} **{nc.description}** ({nc.source_signal}, {nc.severity.value}){occurrence_note}"
    )

    if group.forbidden_variants:
        lines.append(f"  - **DO NOT:** {group.forbidden_variants[0]}")
        if len(group.forbidden_variants) > 1:
            preview = ", ".join(f"`{variant}`" for variant in group.forbidden_variants[1:3])
            remaining = len(group.forbidden_variants) - 3
            suffix = f" (+{remaining} more)" if remaining > 0 else ""
            lines.append(f"  - Pattern variants: {preview}{suffix}")

    if nc.canonical_alternative:
        lines.append(f"  - **INSTEAD:** {nc.canonical_alternative}")

    if nc.affected_files:
        shown = nc.affected_files[:5]
        paths = ", ".join(f"`{f}`" for f in shown)
        suffix = f" (+{len(nc.affected_files) - 5} more)" if len(nc.affected_files) > 5 else ""
        lines.append(f"  - Affected: {paths}{suffix}")

    return "\n".join(lines)


def _group_by_category(
    items: list[NegativeContext],
) -> dict[NegativeContextCategory, list[NegativeContext]]:
    """Group items by category, preserving sort order within groups."""
    groups: dict[NegativeContextCategory, list[NegativeContext]] = {}
    for item in items:
        groups.setdefault(item.category, []).append(item)
    return groups


def _render_prompt_rule(group: _DeduplicatedContext) -> str:
    """Render one compact prompt rule in single-line form."""
    nc = group.item
    do_not = group.forbidden_variants[0] if group.forbidden_variants else nc.description
    instead = nc.canonical_alternative or "Follow established project patterns"
    sev = nc.severity.value.upper()
    suffix = f" (x{group.occurrences})" if group.occurrences > 1 else ""
    return f"- [{sev}|{nc.source_signal}] {do_not} -> {instead}{suffix}"


def _item_to_raw_payload(group: _DeduplicatedContext) -> dict[str, object]:
    """Serialize a NegativeContext item for machine-readable export."""
    nc = group.item
    return {
        "anti_pattern_id": nc.anti_pattern_id,
        "category": nc.category.value,
        "signal": nc.source_signal,
        "severity": nc.severity.value,
        "scope": nc.scope.value,
        "description": nc.description,
        "forbidden_pattern": nc.forbidden_pattern,
        "forbidden_pattern_variants": group.forbidden_variants,
        "canonical_alternative": nc.canonical_alternative,
        "affected_files": nc.affected_files,
        "occurrences": group.occurrences,
        "confidence": nc.confidence,
        "rationale": nc.rationale,
    }


# ---------------------------------------------------------------------------
# Format renderers
# ---------------------------------------------------------------------------


def _render_instructions(
    items: list[NegativeContext],
    drift_score: float,
    severity: Severity,
) -> str:
    """Render as .instructions.md compatible format with YAML front-matter."""
    now = datetime.now(tz=UTC).strftime("%Y-%m-%d")

    lines: list[str] = []
    lines.append("---")
    lines.append('applyTo: "**"')
    lines.append("description: >-")
    lines.append(
        "  Anti-pattern constraints from drift analysis."
        "  DO NOT reproduce these patterns in new code."
    )
    lines.append("---")
    lines.append("")

    lines.append(MARKER_BEGIN)
    lines.append("")
    lines.append("# Anti-Pattern Constraints (drift-generated)")
    lines.append("")
    lines.append(
        "> **These patterns have been detected in this repository."
        " Do NOT reproduce them in new or modified code.**"
    )
    lines.append("")

    lines.append(_render_body(items, drift_score, severity, now))

    lines.append(MARKER_END)
    lines.append("")
    return "\n".join(lines)


def _render_prompt(
    items: list[NegativeContext],
    drift_score: float,
    severity: Severity,
) -> str:
    """Render as compact .prompt.md format for token-efficient prompting."""
    now = datetime.now(tz=UTC).strftime("%Y-%m-%d")

    lines: list[str] = []
    lines.append("---")
    lines.append("mode: agent")
    lines.append("description: >-")
    lines.append("  Anti-pattern constraints from drift analysis.  Consult before generating code.")
    lines.append("---")
    lines.append("")

    lines.append(MARKER_BEGIN)
    lines.append("")
    lines.append("# Repository Anti-Patterns (Compact)")
    lines.append("")
    lines.append("Apply these constraints while generating code. Each rule is `DO_NOT -> INSTEAD`.")
    lines.append("")

    deduped = _deduplicate_items(items)
    for group in deduped:
        lines.append(_render_prompt_rule(group))

    lines.append("")
    lines.append(
        f"Drift snapshot: score={drift_score:.3f}, severity={severity.value},"
        f" rules={len(deduped)}, generated={now}."
    )
    lines.append("For architectural guidance: `drift copilot-context`")
    lines.append("")

    lines.append(MARKER_END)
    lines.append("")
    return "\n".join(lines)


def _render_raw(
    items: list[NegativeContext],
    drift_score: float,
    severity: Severity,
) -> str:
    """Render as machine-readable JSON for orchestration workflows."""
    now = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    deduped = _deduplicate_items(items)
    payload = {
        "format": "drift-negative-context-v1",
        "generated_on": now,
        "drift_score": round(drift_score, 3),
        "drift_score_scope": build_drift_score_scope(context="negative-context:raw"),
        "severity": severity.value,
        "total_items": len(deduped),
        "items": [_item_to_raw_payload(group) for group in deduped],
    }
    return json.dumps(payload, indent=2)


def _render_body(
    items: list[NegativeContext],
    drift_score: float,
    severity: Severity,
    date: str,
) -> str:
    """Render the common body: grouped items + status footer."""
    lines: list[str] = []

    deduped = _deduplicate_items(items)
    grouped_pairs: dict[NegativeContextCategory, list[_DeduplicatedContext]] = {}
    for group in deduped:
        grouped_pairs.setdefault(group.item.category, []).append(group)

    groups: dict[NegativeContextCategory, list[NegativeContext]] = {
        category: [group.item for group in pairs] for category, pairs in grouped_pairs.items()
    }
    category_order = sorted(
        groups,
        key=lambda c: (
            0 if c == NegativeContextCategory.SECURITY else 1,
            -len(groups[c]),
        ),
    )

    for cat in category_order:
        heading = _CATEGORY_HEADING.get(cat, cat.value.title())
        lines.append(f"## {heading}")
        lines.append("")
        for group in grouped_pairs[cat]:
            lines.append(_render_item(group))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        f"*Generated by drift on {date}."
        f" Drift score: {drift_score:.3f} ({severity.value})."
        f" {len(deduped)} anti-patterns detected.*"
    )
    lines.append("")
    lines.append(
        "*For positive architectural guidance (naming conventions, layer boundaries,"
        " code patterns), run: `drift copilot-context`*"
    )
    lines.append("")
    return "\n".join(lines)


_RENDERERS = {
    "instructions": _render_instructions,
    "prompt": _render_prompt,
    "raw": _render_raw,
}


def render_negative_context_markdown(
    items: list[NegativeContext],
    *,
    fmt: str = "instructions",
    drift_score: float = 0.0,
    severity: Severity = Severity.INFO,
) -> str:
    """Render negative context items for the selected format."""
    renderer = _RENDERERS.get(fmt, _render_raw)

    if not items:
        return _render_empty(fmt, drift_score, severity)

    return renderer(items, drift_score, severity)


def _render_empty(
    fmt: str,
    drift_score: float,
    severity: Severity,
) -> str:
    """Render an empty-state document when no anti-patterns are found."""
    now = datetime.now(tz=UTC).strftime("%Y-%m-%d")

    if fmt == "raw":
        payload = {
            "format": "drift-negative-context-v1",
            "generated_on": now,
            "drift_score": round(drift_score, 3),
            "drift_score_scope": build_drift_score_scope(context="negative-context:raw"),
            "severity": severity.value,
            "total_items": 0,
            "items": [],
        }
        return json.dumps(payload, indent=2)

    lines: list[str] = []

    if fmt == "instructions":
        lines.append("---")
        lines.append('applyTo: "**"')
        lines.append("description: >-")
        lines.append("  Anti-pattern constraints from drift analysis.")
        lines.append("---")
        lines.append("")

    if fmt == "prompt":
        lines.append("---")
        lines.append("mode: agent")
        lines.append("description: >-")
        lines.append("  Anti-pattern constraints from drift analysis.")
        lines.append("---")
        lines.append("")

    lines.append(MARKER_BEGIN)
    lines.append("")
    lines.append("# Anti-Pattern Constraints (drift-generated)")
    lines.append("")
    lines.append(
        f"No significant anti-patterns detected. Drift score: {drift_score:.3f} ({severity.value})."
    )
    lines.append("")
    lines.append(f"*Generated by drift on {now}.*")
    lines.append("")
    lines.append(MARKER_END)
    lines.append("")

    return "\n".join(lines)

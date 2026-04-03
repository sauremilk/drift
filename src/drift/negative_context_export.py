"""Render negative context items for agent consumption.

Supports three output formats:
- ``instructions``: compatible with ``.instructions.md`` / copilot-instructions
- ``prompt``: compact summary for system prompt usage
- ``raw``: machine-readable JSON payload for automation pipelines
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime

from drift.models import (
    NegativeContext,
    NegativeContextCategory,
    Severity,
)

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
    "<!-- drift:negative-context:begin"
    " -- auto-generated anti-pattern constraints from drift -->"
)
MARKER_END = "<!-- drift:negative-context:end -->"


def _dedup_key(nc: NegativeContext) -> tuple[str, str, str, str, str]:
    """Return grouping key for semantically identical anti-pattern rules."""
    return (
        nc.category.value,
        nc.source_signal.value,
        nc.severity.value,
        nc.forbidden_pattern or "",
        nc.canonical_alternative or "",
    )


def _deduplicate_items(items: list[NegativeContext]) -> list[tuple[NegativeContext, int]]:
    """Merge duplicate rule entries while preserving first-seen order.

    Rules are considered duplicates when category, signal, severity, and
    DO NOT/INSTEAD patterns are identical. Affected file lists are merged.
    """
    grouped: dict[tuple[str, str, str, str, str], tuple[NegativeContext, int]] = {}
    order: list[tuple[str, str, str, str, str]] = []

    for item in items:
        key = _dedup_key(item)
        if key not in grouped:
            grouped[key] = (
                replace(item, affected_files=list(item.affected_files)),
                1,
            )
            order.append(key)
            continue

        base, count = grouped[key]
        merged_files = list(dict.fromkeys([*base.affected_files, *item.affected_files]))
        grouped[key] = (replace(base, affected_files=merged_files), count + 1)

    return [grouped[key] for key in order]


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _render_item(nc: NegativeContext, occurrences: int = 1) -> str:
    """Render a single NegativeContext as a Markdown list entry."""
    icon = _SEVERITY_ICON.get(nc.severity, "")
    lines: list[str] = []
    occurrence_note = f" ({occurrences} occurrences)" if occurrences > 1 else ""

    lines.append(
        f"- {icon} **{nc.description}** "
        f"({nc.source_signal.value}, {nc.severity.value}){occurrence_note}"
    )

    if nc.forbidden_pattern:
        lines.append(f"  - **DO NOT:** {nc.forbidden_pattern}")

    if nc.canonical_alternative:
        lines.append(f"  - **INSTEAD:** {nc.canonical_alternative}")

    if nc.affected_files:
        shown = nc.affected_files[:5]
        paths = ", ".join(f"`{f}`" for f in shown)
        suffix = (
            f" (+{len(nc.affected_files) - 5} more)"
            if len(nc.affected_files) > 5
            else ""
        )
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


def _render_prompt_rule(nc: NegativeContext, occurrences: int = 1) -> str:
    """Render one compact prompt rule in single-line form."""
    do_not = nc.forbidden_pattern or nc.description
    instead = nc.canonical_alternative or "Follow established project patterns"
    sev = nc.severity.value.upper()
    suffix = f" (x{occurrences})" if occurrences > 1 else ""
    return f"- [{sev}|{nc.source_signal.value}] {do_not} -> {instead}{suffix}"


def _item_to_raw_payload(nc: NegativeContext, occurrences: int = 1) -> dict[str, object]:
    """Serialize a NegativeContext item for machine-readable export."""
    return {
        "anti_pattern_id": nc.anti_pattern_id,
        "category": nc.category.value,
        "signal": nc.source_signal.value,
        "severity": nc.severity.value,
        "scope": nc.scope.value,
        "description": nc.description,
        "forbidden_pattern": nc.forbidden_pattern,
        "canonical_alternative": nc.canonical_alternative,
        "affected_files": nc.affected_files,
        "occurrences": occurrences,
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
    lines.append(
        "  Anti-pattern constraints from drift analysis."
        "  Consult before generating code."
    )
    lines.append("---")
    lines.append("")

    lines.append(MARKER_BEGIN)
    lines.append("")
    lines.append("# Repository Anti-Patterns (Compact)")
    lines.append("")
    lines.append(
        "Apply these constraints while generating code."
        " Each rule is `DO_NOT -> INSTEAD`."
    )
    lines.append("")

    deduped = _deduplicate_items(items)
    for item, occurrences in deduped:
        lines.append(_render_prompt_rule(item, occurrences))

    lines.append("")
    lines.append(
        f"Drift snapshot: score={drift_score:.2f}, severity={severity.value},"
        f" rules={len(deduped)}, generated={now}."
    )
    lines.append(
        "For architectural guidance: `drift copilot-context`"
    )
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
        "drift_score": drift_score,
        "severity": severity.value,
        "total_items": len(deduped),
        "items": [
            _item_to_raw_payload(item, occurrences)
            for item, occurrences in deduped
        ],
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
    grouped_pairs: dict[NegativeContextCategory, list[tuple[NegativeContext, int]]] = {}
    for item, occurrences in deduped:
        grouped_pairs.setdefault(item.category, []).append((item, occurrences))

    groups: dict[NegativeContextCategory, list[NegativeContext]] = {
        category: [item for item, _ in pairs]
        for category, pairs in grouped_pairs.items()
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
        for item, occurrences in grouped_pairs[cat]:
            lines.append(_render_item(item, occurrences))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        f"*Generated by drift on {date}."
        f" Drift score: {drift_score:.2f} ({severity.value})."
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
            "drift_score": drift_score,
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
        "No significant anti-patterns detected."
        f" Drift score: {drift_score:.2f} ({severity.value})."
    )
    lines.append("")
    lines.append(f"*Generated by drift on {now}.*")
    lines.append("")
    lines.append(MARKER_END)
    lines.append("")

    return "\n".join(lines)

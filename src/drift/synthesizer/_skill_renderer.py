"""Repair skill renderer — renders a SkillDraft to SKILL.md text.

This module produces the *text content* of a repair SKILL.md from a
serialised ``SkillDraft``.  It is intentionally free of I/O; callers
are responsible for writing the result to disk.

Usage::

    from drift.synthesizer._skill_renderer import render_repair_skill_md
    text = render_repair_skill_md(draft.to_dict())
"""

from __future__ import annotations

from typing import Any


def render_repair_skill_md(draft: dict[str, Any]) -> str:
    """Render a *repair* skill draft to SKILL.md text.

    Parameters
    ----------
    draft:
        A ``SkillDraft.to_dict()`` result.

    Returns
    -------
    str
        Complete SKILL.md content for a repair skill.
    """
    signals_str = ", ".join(draft.get("trigger_signals", []))
    conf_str = str(draft.get("confidence", "?"))
    module = draft.get("module_path", "?")

    lines: list[str] = []

    # --- YAML frontmatter --------------------------------------------------
    description = (
        f"Drift-generierter Repair-Skill fuer `{module}`. "
        f"Aktiv bei Signalen: {signals_str}. "
        f"Konfidenz: {conf_str}. "
        f"Verwende diesen Skill wenn du bestehende {signals_str}-Findings "
        f"in `{module}` beheben willst."
    )
    lines += [
        "---",
        f"name: {draft.get('name', 'repair-unknown')}",
        f'description: "{description}"',
        "---",
        "",
        f"# Repair: `{module}`",
        "",
        "Automatisch generiert von `drift synthesize`.",
        f"Konfidenz: **{conf_str}** | Signale: **{signals_str}**",
        "",
    ]

    # --- Trigger -----------------------------------------------------------
    lines += ["## Trigger", "", draft.get("trigger", "\u2014"), ""]

    # --- Goal --------------------------------------------------------------
    lines += ["## Goal", "", draft.get("goal", "\u2014"), ""]

    # --- Fix Patterns ------------------------------------------------------
    fix_patterns = draft.get("fix_patterns", [])
    if fix_patterns:
        lines += ["## Fix Patterns", ""]
        for pattern in fix_patterns:
            lines.append(f"- {pattern}")
        lines.append("")

    # --- Constraints -------------------------------------------------------
    constraints = draft.get("constraints", [])
    if constraints:
        lines += ["## Constraints", ""]
        for c in constraints:
            lines.append(f"- {c}")
        lines.append("")

    # --- Negative Examples (don't apply when...) ---------------------------
    negatives = draft.get("negative_examples", [])
    if negatives:
        lines += ["## Negative Examples", ""]
        for ex in negatives:
            lines.append(f"- {ex}")
        lines.append("")

    # --- Verify Commands ---------------------------------------------------
    verify = draft.get("verify_commands", [])
    if verify:
        lines += ["## Verify", ""]
        for cmd in verify:
            lines.append(f"- `{cmd}`")
        lines.append("")

    # --- References --------------------------------------------------------
    lines += ["## References", ""]
    lines.append("- [DEVELOPER.md](../../../DEVELOPER.md)")
    lines.append("- [POLICY.md](../../../POLICY.md)")
    lines.append("")

    return "\n".join(lines)

"""Skill-briefing writer — renders a ``SkillBriefing`` to SKILL.md text.

This module produces the *text content* of a SKILL.md guard file from a
structured ``SkillBriefing``.  It is intentionally free of I/O; callers
are responsible for writing the result to disk.

Usage::

    from drift.arch_graph._skill_writer import render_skill_md
    text = render_skill_md(briefing)
    Path(".github/skills/guard-x/SKILL.md").write_text(text, encoding="utf-8")
"""

from __future__ import annotations

from drift.arch_graph._models import SkillBriefing

# ---------------------------------------------------------------------------
# Signal-specific When-To-Use hints
# ---------------------------------------------------------------------------

_SIGNAL_WHEN_TO_USE: dict[str, str] = {
    "AVS": (
        "Du aenderst wie Dateien oder Symbole gelesen, geparst oder aggregiert werden"
        " (zu viele Verantwortlichkeiten pro Modul)."
    ),
    "EDS": (
        "Du veraenderst Abhaengigkeiten zwischen Modulen oder fuegest neuen"
        " Crosscutting-Code hinzu."
    ),
    "MDS": (
        "Du aenderst den Kontrollfluss oder fuegest neue Abzweigungen hinzu"
        " (hohe zyklomatische Komplexitaet)."
    ),
    "PFS": (
        "Du aenderst oeffentliche API-Signaturen, ergaenzt neue Exports oder"
        " veraenderst das Fehlerbehandlungsmuster."
    ),
}

_SIGNAL_CORE_RULE: dict[str, str] = {
    "AVS": (
        "Behalte eine klar abgegrenzte Verantwortlichkeit pro Funktion und Klasse"
        " — kein Mischen von Parse-, Berechungs- und IO-Logik."
    ),
    "EDS": (
        "Importiere ausschliesslich aus deklarierten Abhaengigkeiten"
        " — kein Zugriff ueber Modulgrenzen auf interne Symbole."
    ),
    "MDS": (
        "Halte zyklomatische Komplexitaet <= 10 pro Funktion;"
        " extrahiere Kontrollfluss in benannte Hilfs-Funktionen."
    ),
    "PFS": (
        "Oeffentliche Funktionen und Klassen benoetigen Docstrings und stabile Signaturen"
        " — Breaking Changes erfordern Deprecation-Marker."
    ),
}

_SIGNAL_CHECKLIST_ITEM: dict[str, str] = {
    "AVS": "Keine neuen AVS-Findings (zu viele Verantwortlichkeiten)",
    "EDS": "Keine neuen EDS-Findings (undeklarierte Abhaengigkeiten)",
    "MDS": "Keine neuen MDS-Findings (hohe Komplexitaet)",
    "PFS": "Keine neuen PFS-Findings (fehlende Docstrings / instabile API)",
}


# ---------------------------------------------------------------------------
# Public renderer
# ---------------------------------------------------------------------------


def render_skill_md(briefing: SkillBriefing) -> str:
    """Render *briefing* to SKILL.md text.

    The output follows the same structural template as hand-crafted Drift
    guard skills: YAML frontmatter, section headers, checklist.

    Parameters
    ----------
    briefing:
        A populated ``SkillBriefing`` as returned by
        ``generate_skill_briefings()``.

    Returns
    -------
    str
        Complete SKILL.md content, UTF-8 safe, no trailing newline after final line.
    """
    signals_str = ", ".join(briefing.trigger_signals)
    conf_str = str(briefing.confidence)

    lines: list[str] = []

    # --- YAML frontmatter --------------------------------------------------
    description = (
        f"Drift-generierter Guard fuer `{briefing.module_path}`. "
        f"Aktiv bei Signalen: {signals_str}. "
        f"Konfidenz: {conf_str}. "
        f"Verwende diesen Skill wenn du Aenderungen an `{briefing.module_path}` "
        f"planst oder wiederholte Drift-Findings ({signals_str}) fuer dieses Modul bearbeitest."
    )
    argument_hint = (
        f"Beschreibe die geplante Aenderung in `{briefing.module_path}` — "
        "welche Funktion, welches Modul, welche Schnittstelle."
    )
    lines += [
        "---",
        f"name: {briefing.name}",
        f'description: "{description}"',
        f'argument-hint: "{argument_hint}"',
        "---",
        "",
    ]

    # --- Header ------------------------------------------------------------
    lines += [
        f"# Guard: `{briefing.module_path}`",
        "",
        "Automatisch generiert von `drift generate-skills`.",
        f"Konfidenz: **{conf_str}** | Signale: **{signals_str}**",
        "",
    ]

    # --- When To Use -------------------------------------------------------
    lines += ["## When To Use", ""]
    for signal in briefing.trigger_signals:
        hint = _SIGNAL_WHEN_TO_USE.get(
            signal,
            f"Drift meldet {signal}-Findings in `{briefing.module_path}`.",
        )
        lines.append(f"- {hint}")
    for f in briefing.hotspot_files:
        lines.append(f"- Du aenderst `{f}`.")
    lines.append("")

    # --- Core Rules --------------------------------------------------------
    lines += ["## Core Rules", ""]
    rule_idx = 1
    for signal in briefing.trigger_signals:
        rule_text = _SIGNAL_CORE_RULE.get(
            signal,
            f"Vermeide neue {signal}-Findings in `{briefing.module_path}`.",
        )
        lines.append(f"{rule_idx}. **{signal}** — {rule_text}")
        rule_idx += 1
    for c in briefing.constraints:
        rule = c.get("rule", "")
        enforcement = c.get("enforcement", "warn")
        lines.append(f"{rule_idx}. **{enforcement.upper()}** — {rule}")
        rule_idx += 1
    lines.append("")

    # --- Architecture Context ----------------------------------------------
    layer_label = briefing.layer or "unbekannt"
    neighbors_str = (
        ", ".join(f"`{n}`" for n in briefing.neighbors)
        if briefing.neighbors
        else "—"
    )
    abstractions_str = (
        ", ".join(f"`{a}`" for a in briefing.abstractions)
        if briefing.abstractions
        else "—"
    )
    lines += [
        "## Architecture Context",
        "",
        f"- **Layer**: {layer_label}",
        f"- **Nachbarmodule**: {neighbors_str}",
        f"- **Wiederverwendete Abstraktionen**: {abstractions_str}",
        "",
    ]

    # --- Review Checklist --------------------------------------------------
    lines += ["## Review Checklist", ""]
    lines.append("- [ ] `drift nudge` zeigt `safe_to_commit: true`")
    for signal in briefing.trigger_signals:
        item = _SIGNAL_CHECKLIST_ITEM.get(signal, f"Keine neuen {signal}-Findings")
        lines.append(f"- [ ] {item}")
    for c in briefing.constraints:
        rule = c.get("rule", "")
        if rule:
            lines.append(f"- [ ] {rule}")
    lines.append("")

    # --- References --------------------------------------------------------
    lines += ["## References", ""]
    lines.append("- [DEVELOPER.md](../../../DEVELOPER.md)")
    lines.append("- [POLICY.md](../../../POLICY.md)")
    for f in briefing.hotspot_files:
        lines.append(f"- [{f}](../../../{f})")
    lines.append("")

    return "\n".join(lines)

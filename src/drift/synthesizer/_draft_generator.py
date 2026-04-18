"""Draft generator — creates guard and repair skill drafts from clusters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from drift.signal_registry import get_meta, get_signal_to_abbrev
from drift.synthesizer._models import FindingCluster, SkillDraft

if TYPE_CHECKING:
    pass  # ArchGraph type used via Any to avoid import issues

# ---------------------------------------------------------------------------
# Signal-specific description templates
# ---------------------------------------------------------------------------

_SIGNAL_TRIGGER_HINT: dict[str, str] = {
    "AVS": "Modul hat wiederholt zu viele Verantwortlichkeiten (Abstraction Violation).",
    "EDS": "Undeklarierte oder implizite Abhaengigkeiten zwischen Modulen.",
    "MDS": "Hohe zyklomatische Komplexitaet und Kontrollfluss-Verschachtelung.",
    "PFS": "Fehlende Docstrings oder instabile oeffentliche API-Signaturen.",
    "CCC": "Co-Change Coupling: Dateien aendern sich staendig gemeinsam.",
    "DIA": "Dokumentation und Implementierung driften auseinander.",
    "BEM": "Broad Exception Monoculture: zu breite except-Klauseln.",
    "GCD": "Guard Clause Deficit: verschachtelte Bedingungen statt fruehe Returns.",
    "BAT": "Bypass Accumulation: wachsende Anzahl von Sonderfaellen und Workarounds.",
    "NBV": "Naming Contract Violation: inkonsistente Benennungskonventionen.",
}

_SIGNAL_GOAL_HINT: dict[str, str] = {
    "AVS": "Verantwortlichkeiten klar trennen, God-Module aufloesen.",
    "EDS": "Abhaengigkeiten explizit deklarieren, interne Symbole kapseln.",
    "MDS": "Kontrollfluss vereinfachen, Hilfsfunktionen extrahieren.",
    "PFS": "API-Stabilitaet sichern, Docstrings ergaenzen.",
    "CCC": "Kopplung reduzieren, unabhaengige Module entkoppeln.",
    "DIA": "Dokumentation mit Implementierung synchron halten.",
    "BEM": "Spezifische Exceptions verwenden statt breiter Catches.",
    "GCD": "Guard Clauses einsetzen, Verschachtelungstiefe reduzieren.",
    "BAT": "Workarounds konsolidieren oder durch saubere Loesung ersetzen.",
    "NBV": "Benennungskonventionen konsistent durchsetzen.",
}

_REPAIR_WORKFLOW: dict[str, str] = {
    "verifiable": "Automatisiert pruefbar — `drift verify` bestaetigt den Fix.",
    "plannable": "Planbar — der Fix erfordert gezielte Aenderungen in bekannten Dateien.",
    "example_based": "Beispielbasiert — orientiere dich an den Negativbeispielen.",
    "diagnosis": "Diagnose noetig — Ursache vor dem Fix verstehen.",
}


def _to_kebab(module_path: str) -> str:
    """Convert a module path to kebab-case for skill naming."""
    return module_path.replace("/", "-").replace("\\", "-").replace("_", "-").lower()


def _signal_abbrev(signal_type: str) -> str:
    """Get abbreviation for a signal type."""
    abbrev_map = get_signal_to_abbrev()
    return abbrev_map.get(signal_type, signal_type[:3].upper())


def _get_repair_level(signal_type: str) -> str:
    """Look up the repair level from the signal registry."""
    meta = get_meta(signal_type)
    return meta.repair_level if meta else "diagnosis"


def generate_skill_drafts(
    clusters: list[FindingCluster],
    graph: Any = None,
    *,
    kinds: Literal["guard", "repair", "all"] = "all",
) -> list[SkillDraft]:
    """Generate guard and/or repair skill drafts from finding clusters.

    Parameters
    ----------
    clusters:
        Finding clusters from ``build_finding_clusters()``.
    graph:
        Optional architecture graph for module metadata enrichment.
    kinds:
        Which skill types to generate.

    Returns
    -------
    list[SkillDraft]
        Skill drafts sorted by confidence descending.
    """
    drafts: list[SkillDraft] = []
    for cluster in clusters:
        if kinds in ("guard", "all"):
            drafts.append(_build_guard_draft(cluster, graph))
        if kinds in ("repair", "all"):
            drafts.append(_build_repair_draft(cluster, graph))

    drafts.sort(key=lambda d: d.confidence, reverse=True)
    return drafts


def _build_guard_draft(
    cluster: FindingCluster,
    graph: Any,
) -> SkillDraft:
    """Build a preventive guard skill draft."""
    abbrev = _signal_abbrev(cluster.signal_type)
    module_kebab = _to_kebab(cluster.module_path)
    name = f"guard-{module_kebab}"

    trigger = _SIGNAL_TRIGGER_HINT.get(
        abbrev,
        f"Drift meldet wiederholt {abbrev}-Findings in `{cluster.module_path}`.",
    )
    goal = _SIGNAL_GOAL_HINT.get(
        abbrev,
        f"Neue {abbrev}-Findings in `{cluster.module_path}` verhindern.",
    )

    constraints = _extract_constraints(cluster, graph)
    negative_examples = _extract_negative_examples(cluster)
    confidence = _compute_draft_confidence(cluster, graph)

    return SkillDraft(
        kind="guard",
        name=name,
        module_path=cluster.module_path,
        trigger=trigger,
        goal=goal,
        trigger_signals=[abbrev],
        constraints=constraints,
        negative_examples=negative_examples,
        fix_patterns=[],
        verify_commands=[
            f"drift analyze --repo . --scope {cluster.module_path} --exit-zero",
            "drift nudge",
        ],
        source_cluster=cluster,
        confidence=confidence,
    )


def _build_repair_draft(
    cluster: FindingCluster,
    graph: Any,
) -> SkillDraft:
    """Build an active repair skill draft."""
    abbrev = _signal_abbrev(cluster.signal_type)
    module_kebab = _to_kebab(cluster.module_path)
    name = f"repair-{abbrev.lower()}-{module_kebab}"

    repair_level = _get_repair_level(cluster.signal_type)
    trigger = _SIGNAL_TRIGGER_HINT.get(
        abbrev,
        f"Drift meldet {abbrev}-Findings in `{cluster.module_path}` die behoben werden muessen.",
    )
    goal = (
        f"Bestehende {abbrev}-Findings in `{cluster.module_path}` beheben. "
        f"Repair-Level: {repair_level}."
    )

    constraints = _extract_constraints(cluster, graph)
    negative_examples = _extract_negative_examples(cluster)
    fix_patterns = _extract_fix_patterns(cluster, repair_level)
    confidence = _compute_draft_confidence(cluster, graph)

    return SkillDraft(
        kind="repair",
        name=name,
        module_path=cluster.module_path,
        trigger=trigger,
        goal=goal,
        trigger_signals=[abbrev],
        constraints=constraints,
        negative_examples=negative_examples,
        fix_patterns=fix_patterns,
        verify_commands=[
            f"drift analyze --repo . --scope {cluster.module_path} --exit-zero",
            "drift verify",
        ],
        source_cluster=cluster,
        confidence=confidence,
    )


def _extract_constraints(
    cluster: FindingCluster,
    graph: Any,
) -> list[str]:
    """Extract relevant constraints from ArchGraph decisions."""
    if graph is None:
        return []
    decisions = getattr(graph, "decisions", [])
    if not decisions:
        return []
    constraints: list[str] = []
    for decision in decisions:
        if not getattr(decision, "active", True):
            continue
        scope = getattr(decision, "scope", "").rstrip("*").rstrip("/")
        if cluster.module_path.startswith(scope):
            enforcement = getattr(decision, "enforcement", "warn")
            rule = getattr(decision, "rule", "")
            constraints.append(f"[{enforcement.upper()}] {rule}")
    return constraints


def _extract_negative_examples(cluster: FindingCluster) -> list[str]:
    """Derive 'don't apply when...' hints from FP feedback."""
    examples: list[str] = []
    if cluster.feedback.fp > 0:
        examples.append(
            f"Nicht anwenden wenn der Befund ein bekanntes False Positive ist "
            f"({cluster.feedback.fp} FP in Feedback-Historie)."
        )
    return examples


def _extract_fix_patterns(
    cluster: FindingCluster,
    repair_level: str,
) -> list[str]:
    """Aggregate fix hints for repair drafts."""
    workflow = _REPAIR_WORKFLOW.get(repair_level, "Diagnose noetig.")
    patterns = [f"Repair-Workflow: {workflow}"]
    # Deduplicate file mentions for targeted guidance
    if cluster.affected_files:
        top_files = cluster.affected_files[:5]
        patterns.append(
            "Betroffene Dateien: " + ", ".join(f"`{f}`" for f in top_files),
        )
    return patterns


def _compute_draft_confidence(
    cluster: FindingCluster,
    graph: Any = None,
) -> float:
    """Compute confidence score for a draft.

    Combines cluster recurrence rate with trend and feedback quality.
    """
    base = 0.5 + (min(cluster.recurrence_rate, 1.0) * 0.3)

    # Boost for degrading trend
    if cluster.trend == "degrading":
        base = min(base + 0.1, 1.0)

    # Boost for strong feedback evidence
    if cluster.feedback.total >= 5 and cluster.feedback.precision >= 0.8:
        base = min(base + 0.05, 1.0)

    # Penalty for high FP rate
    if cluster.feedback.total >= 3 and cluster.feedback.precision < 0.5:
        base = max(base - 0.1, 0.3)

    return round(base, 2)

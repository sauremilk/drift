"""Guided output layer — traffic-light status and plain-language signal texts.

Translates ``RepoAnalysis`` results into an everyday-language format
designed for users without software-architecture expertise (Persona A / Vibe-Coder).
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from drift.models import RepoAnalysis

# ---------------------------------------------------------------------------
# Traffic-light status
# ---------------------------------------------------------------------------

_DEFAULT_THRESHOLDS: dict[str, float] = {"green_max": 0.35, "yellow_max": 0.65}


class TrafficLight(StrEnum):
    """Three-state project health indicator."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


def determine_status(
    analysis: RepoAnalysis,
    thresholds: dict[str, float] | None = None,
) -> TrafficLight:
    """Compute traffic-light status from analysis results.

    RED has unconditional priority over YELLOW (PRD F-02).

    Parameters
    ----------
    analysis:
        Completed repository analysis.
    thresholds:
        ``{"green_max": float, "yellow_max": float}`` boundaries.
        Falls back to calibrated vibe-coding defaults when *None* or empty.
    """
    t = thresholds if thresholds else _DEFAULT_THRESHOLDS
    green_max = t.get("green_max", 0.35)
    yellow_max = t.get("yellow_max", 0.65)

    has_critical = any(f.severity.value == "critical" for f in analysis.findings)
    has_high = any(f.severity.value == "high" for f in analysis.findings)
    score = analysis.drift_score

    # RED: score >= yellow_max OR any CRITICAL finding
    if score >= yellow_max or has_critical:
        return TrafficLight.RED

    # YELLOW: score >= green_max OR any HIGH finding
    if score >= green_max or has_high:
        return TrafficLight.YELLOW

    return TrafficLight.GREEN


def can_continue(status: TrafficLight) -> bool:
    """Semantic signal for integrating tools — ``True`` only for GREEN."""
    return status is TrafficLight.GREEN


# ---------------------------------------------------------------------------
# Headlines (everyday German)
# ---------------------------------------------------------------------------

_HEADLINES: dict[TrafficLight, str] = {
    TrafficLight.GREEN: "Dein Projekt sieht gut aus. Du kannst weiterarbeiten.",
    TrafficLight.YELLOW: "Es gibt Stellen, die Aufmerksamkeit brauchen.",
    TrafficLight.RED: (
        "Dein Projekt hat ein strukturelles Problem, "
        "das du jetzt angehen solltest."
    ),
}


def headline_for_status(status: TrafficLight) -> str:
    """Return an everyday-language headline for the given status."""
    return _HEADLINES[status]


# ---------------------------------------------------------------------------
# Emoji rendering
# ---------------------------------------------------------------------------

_EMOJI: dict[TrafficLight, str] = {
    TrafficLight.GREEN: "\U0001f7e2",   # 🟢
    TrafficLight.YELLOW: "\U0001f7e1",  # 🟡
    TrafficLight.RED: "\U0001f534",     # 🔴
}


def emoji_for_status(status: TrafficLight) -> str:
    """Return the traffic-light emoji for terminal rendering."""
    return _EMOJI[status]


# ---------------------------------------------------------------------------
# Severity labels (German, no technical jargon)
# ---------------------------------------------------------------------------

_SEVERITY_LABELS: dict[str, str] = {
    "critical": "Kritisch",
    "high": "Wichtig",
    "medium": "Auffällig",
    "low": "Hinweis",
    "info": "Info",
}


def severity_label(severity: str) -> str:
    """German everyday label for a severity value."""
    return _SEVERITY_LABELS.get(severity, severity)


# ---------------------------------------------------------------------------
# Calibration hint
# ---------------------------------------------------------------------------


def is_calibrated(thresholds: dict[str, float] | None) -> bool:
    """Return True when the profile provides explicit guided thresholds."""
    return bool(thresholds)


# ---------------------------------------------------------------------------
# Plain-language signal descriptions (German, all scoring-active signals)
# ---------------------------------------------------------------------------

SIGNAL_PLAIN_TEXT: dict[str, str] = {
    # --- 15 original core signals (excluding temporal_volatility = report-only) ---
    "pattern_fragmentation": (
        "Dasselbe wird an mehreren Stellen auf unterschiedliche Art gelöst."
    ),
    "architecture_violation": (
        "Code greift auf Bereiche zu, die eigentlich getrennt sein sollten."
    ),
    "mutant_duplicate": (
        "Es gibt fast identische Code-Abschnitte mit kleinen Abweichungen."
    ),
    "explainability_deficit": (
        "Teile des Codes sind schwer nachvollziehbar — zu komplex oder zu verschachtelt."
    ),
    "doc_impl_drift": (
        "Die Dokumentation passt nicht mehr zum tatsächlichen Code."
    ),
    "system_misalignment": (
        "Die Projektstruktur entspricht nicht dem, was der Code tatsächlich tut."
    ),
    "broad_exception_monoculture": (
        "Fehler werden zu allgemein abgefangen — spezifische Probleme gehen verloren."
    ),
    "test_polarity_deficit": (
        "Tests prüfen nur den Normalfall, aber nicht was bei Fehlern passieren soll."
    ),
    "guard_clause_deficit": (
        "Funktionen prüfen Eingaben nicht früh genug und werden dadurch unübersichtlich."
    ),
    "naming_contract_violation": (
        "Benennungen im Code sind inkonsistent oder irreführend."
    ),
    "bypass_accumulation": (
        "Es gibt viele Stellen, an denen Qualitätsprüfungen übersprungen werden."
    ),
    "exception_contract_drift": (
        "Fehlermeldungen sind inkonsistent — verschiedene Stellen werfen "
        "unterschiedliche Fehlertypen."
    ),
    "cohesion_deficit": (
        "Einzelne Dateien oder Klassen machen zu viele verschiedene Dinge."
    ),
    "co_change_coupling": (
        "Bestimmte Dateien müssen immer zusammen geändert werden — ein Zeichen "
        "versteckter Abhängigkeiten."
    ),
    # --- 3 promoted signals (ADR-040) ---
    "fan_out_explosion": (
        "Einzelne Dateien importieren zu viele andere Module — ein Änderungs-Risiko."
    ),
    "hardcoded_secret": (
        "Es gibt fest eingebaute Zugangsdaten oder Schlüssel im Code."
    ),
    "phantom_reference": (
        "Der Code verweist auf Funktionen oder Module, die nicht mehr existieren."
    ),
    # --- Report-only signals (included for completeness) ---
    "temporal_volatility": (
        "Bestimmte Dateien werden ungewöhnlich häufig geändert."
    ),
    "ts_architecture": (
        "TypeScript-Code hat strukturelle Probleme."
    ),
    "cognitive_complexity": (
        "Funktionen sind zu komplex verschachtelt und schwer zu verstehen."
    ),
    "circular_import": (
        "Module importieren sich gegenseitig — das kann zu Startproblemen führen."
    ),
    "dead_code_accumulation": (
        "Es gibt ungenutzten Code, der das Projekt unübersichtlicher macht."
    ),
    "missing_authorization": (
        "Bestimmte Endpunkte haben möglicherweise keine Zugriffsprüfung."
    ),
    "insecure_default": (
        "Sicherheitsrelevante Einstellungen verwenden unsichere Standardwerte."
    ),
    "type_safety_bypass": (
        "Typ-Prüfungen werden an mehreren Stellen umgangen."
    ),
}

# Set of signal types that are scoring-active (weight > 0 in default profile)
SCORING_ACTIVE_SIGNALS: frozenset[str] = frozenset({
    "pattern_fragmentation",
    "architecture_violation",
    "mutant_duplicate",
    "explainability_deficit",
    "doc_impl_drift",
    "system_misalignment",
    "broad_exception_monoculture",
    "test_polarity_deficit",
    "guard_clause_deficit",
    "naming_contract_violation",
    "bypass_accumulation",
    "exception_contract_drift",
    "cohesion_deficit",
    "co_change_coupling",
    "fan_out_explosion",
    "hardcoded_secret",
    "phantom_reference",
})


def plain_text_for_signal(signal_type: str) -> str:
    """Return the plain-language description for a signal type.

    Falls back to the raw signal type name if no mapping exists.
    """
    return SIGNAL_PLAIN_TEXT.get(signal_type, signal_type)


# ---------------------------------------------------------------------------
# Guided finding dict (for JSON output)
# ---------------------------------------------------------------------------


def guided_finding_dict(
    finding: Any,
    *,
    agent_prompt: str,
) -> dict[str, Any]:
    """Build a guided-mode finding dict for JSON output.

    Parameters
    ----------
    finding:
        A ``Finding`` instance.
    agent_prompt:
        Pre-generated agent prompt text.
    """
    return {
        "plain_text": plain_text_for_signal(finding.signal_type),
        "agent_prompt": agent_prompt,
        "severity_label": severity_label(finding.severity.value),
    }

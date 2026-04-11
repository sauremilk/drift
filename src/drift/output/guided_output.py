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
# Headlines — German (default) and English variants
# ---------------------------------------------------------------------------

_HEADLINES: dict[TrafficLight, str] = {
    TrafficLight.GREEN: "Dein Projekt sieht gut aus. Du kannst weiterarbeiten.",
    TrafficLight.YELLOW: "Es gibt Stellen, die Aufmerksamkeit brauchen.",
    TrafficLight.RED: (
        "Dein Projekt hat ein strukturelles Problem, "
        "das du jetzt angehen solltest."
    ),
}

_HEADLINES_EN: dict[TrafficLight, str] = {
    TrafficLight.GREEN: "Your project looks healthy. You can keep coding.",
    TrafficLight.YELLOW: "There are areas that need attention.",
    TrafficLight.RED: "Your project has a structural issue you should address now.",
}


def headline_for_status(status: TrafficLight, language: str = "de") -> str:
    """Return an everyday-language headline for the given status."""
    if language.startswith("en"):
        return _HEADLINES_EN[status]
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
# Severity labels — German (default) and English variants
# ---------------------------------------------------------------------------

_SEVERITY_LABELS: dict[str, str] = {
    "critical": "Kritisch",
    "high": "Wichtig",
    "medium": "Auffällig",
    "low": "Hinweis",
    "info": "Info",
}

_SEVERITY_LABELS_EN: dict[str, str] = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "info": "Info",
}


def severity_label(severity: str, language: str = "de") -> str:
    """Everyday label for a severity value.

    Parameters
    ----------
    severity:
        Raw severity string (e.g. ``"high"``).
    language:
        ``"en"`` for English labels; ``"de"`` (default) for German labels.
    """
    if language.startswith("en"):
        return _SEVERITY_LABELS_EN.get(severity, severity)
    return _SEVERITY_LABELS.get(severity, severity)


# ---------------------------------------------------------------------------
# Calibration hint
# ---------------------------------------------------------------------------


def is_calibrated(thresholds: dict[str, float] | None) -> bool:
    """Return True when the profile provides explicit guided thresholds."""
    return bool(thresholds)


# ---------------------------------------------------------------------------
# Plain-language signal descriptions — German (default) and English variants
# ---------------------------------------------------------------------------

SIGNAL_PLAIN_TEXT_EN: dict[str, str] = {
    "pattern_fragmentation": "The same concept is solved multiple ways across the module.",
    "architecture_violation": "Code accesses layers it should not depend on directly.",
    "mutant_duplicate": "Near-identical code blocks diverge in subtle ways.",
    "explainability_deficit": "Complex code lacks documentation or clear naming.",
    "doc_impl_drift": "Documentation no longer matches the actual implementation.",
    "system_misalignment": "New code introduces conventions that conflict with the module norm.",
    "broad_exception_monoculture": "Exceptions are caught too broadly, silencing specific errors.",
    "test_polarity_deficit": "Tests only cover the happy path — failure cases are not tested.",
    "guard_clause_deficit": "Missing early returns create deep nesting that is hard to follow.",
    "naming_contract_violation": "Names are inconsistent with project naming conventions.",
    "bypass_accumulation": "Growing number of bypassed quality checks signals deferred debt.",
    "exception_contract_drift": "Raised exceptions diverge from the declared error contract.",
    "cohesion_deficit": "A file or class handles too many unrelated responsibilities.",
    "co_change_coupling": "Files that always change together hide an implicit shared dependency.",
    "fan_out_explosion": "A module imports too many others, creating fragile coupling.",
    "hardcoded_secret": "Credentials or secrets are hardcoded in source files.",
    "phantom_reference": "Code references functions or modules that no longer exist.",
    "temporal_volatility": "Certain files change unusually often.",
    "ts_architecture": "TypeScript code has structural problems.",
    "cognitive_complexity": "Functions are nested too deeply and are hard to reason about.",
    "circular_import": "Modules import each other, creating fragile load-order dependencies.",
    "dead_code_accumulation": "Unreachable code clutters the codebase.",
    "missing_authorization": "Certain endpoints may lack an authorization check.",
    "insecure_default": "Security-relevant settings use insecure default values.",
    "type_safety_bypass": "Type checks are bypassed in multiple places.",
}

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


def plain_text_for_signal(signal_type: str, language: str = "de") -> str:
    """Return the plain-language description for a signal type.

    Parameters
    ----------
    signal_type:
        Signal type string (e.g. ``"pattern_fragmentation"``).
    language:
        ``"en"`` for English descriptions; ``"de"`` (default) for German.

    Falls back to the raw signal type name if no mapping exists.
    """
    if language.startswith("en"):
        return SIGNAL_PLAIN_TEXT_EN.get(signal_type, signal_type)
    return SIGNAL_PLAIN_TEXT.get(signal_type, signal_type)


# ---------------------------------------------------------------------------
# Profile-aware score context
# ---------------------------------------------------------------------------

# Typical healthy score ranges per profile (derived from benchmark data).
_PROFILE_CONTEXT: dict[str, dict[str, str]] = {
    "vibe-coding": {
        "range": "0.20–0.50",
        "note_en": (
            "Vibe-coding profile: AI-assisted projects typically score "
            "0.20–0.50 on first scan."
        ),
        "note_de": (
            "Vibe-Coding Profil: KI-unterstützte Projekte liegen beim ersten "
            "Scan meist bei 0.20–0.50."
        ),
    },
    "default": {
        "range": "0.25–0.55",
        "note_en": "Default profile: fresh projects typically score 0.25–0.55 on first scan.",
        "note_de": "Standard-Profil: Neue Projekte liegen beim ersten Scan meist bei 0.25–0.55.",
    },
    "strict": {
        "range": "0.30–0.65",
        "note_en": "Strict profile: scores above 0.45 warrant attention.",
        "note_de": "Striktes Profil: Scores über 0.45 sollten beachtet werden.",
    },
}


def profile_score_context(profile_name: str, language: str = "en") -> str | None:
    """Return a short contextual note about the score range for a given profile.

    Returns ``None`` when no context is available for the profile.
    """
    ctx = _PROFILE_CONTEXT.get(profile_name)
    if ctx is None:
        return None
    key = "note_de" if language.startswith("de") else "note_en"
    return ctx[key]


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

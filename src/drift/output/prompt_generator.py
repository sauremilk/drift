"""Template-based prompt generation for guided mode.

Generates copy-paste-ready prompts in everyday German that users
can feed directly to their AI assistant to fix structural issues.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# File-role heuristics  (PRD F-06: no raw file paths)
# ---------------------------------------------------------------------------

_DIR_ROLES: dict[str, str] = {
    "api": "die API-Logik",
    "routes": "die API-Routen",
    "views": "die View-Logik",
    "auth": "die Authentifizierung",
    "login": "die Login-Logik",
    "db": "die Datenbankschicht",
    "database": "die Datenbankschicht",
    "models": "die Datenmodelle",
    "schemas": "die Datenschemata",
    "services": "die Service-Schicht",
    "utils": "die Hilfsfunktionen",
    "helpers": "die Hilfsfunktionen",
    "lib": "die Bibliotheksmodule",
    "core": "die Kernlogik",
    "config": "die Konfiguration",
    "settings": "die Einstellungen",
    "tests": "die Tests",
    "test": "die Tests",
    "middleware": "die Middleware",
    "handlers": "die Handler-Logik",
    "commands": "die CLI-Kommandos",
    "cli": "die Kommandozeile",
    "output": "die Ausgabelogik",
    "templates": "die Vorlagen",
    "static": "die statischen Dateien",
    "frontend": "das Frontend",
    "backend": "das Backend",
    "server": "den Server",
    "client": "den Client",
    "components": "die Komponenten",
    "pages": "die Seiten",
    "hooks": "die Hooks",
    "store": "den State-Store",
    "state": "die Zustandsverwaltung",
    "types": "die Typdefinitionen",
    "interfaces": "die Schnittstellen",
    "plugins": "die Plugins",
    "extensions": "die Erweiterungen",
    "migrations": "die Datenbankmigrationen",
    "scripts": "die Skripte",
    "tasks": "die Hintergrundaufgaben",
    "workers": "die Worker-Prozesse",
    "signals": "die Signal-Erkennung",
    "scoring": "die Bewertungslogik",
    "ingestion": "die Datenaufnahme",
}


def file_role_description(finding: Any) -> str:
    """Derive a functional role description from a finding's location.

    Uses ``logical_location`` when available, then falls back to
    directory-name heuristics.  Never returns the raw file path.
    """
    # 1. Prefer logical_location (AST-based, most precise)
    ll = getattr(finding, "logical_location", None)
    if ll is not None:
        kind = getattr(ll, "kind", "")
        name = getattr(ll, "name", "")
        class_name = getattr(ll, "class_name", None)
        if kind == "method" and class_name and name:
            return f"die Methode \u201e{name}\u201c in der Klasse \u201e{class_name}\u201c"
        if kind == "function" and name:
            return f"die Funktion \u201e{name}\u201c"
        if kind == "class" and name:
            return f"die Klasse \u201e{name}\u201c"
        if kind == "module" and name:
            return f"das Modul \u201e{name}\u201c"

    # 2. Directory heuristic from file_path
    fp = getattr(finding, "file_path", None)
    if fp is not None:
        parts = PurePosixPath(str(fp)).parts
        for part in reversed(parts[:-1]):  # skip filename itself
            role = _DIR_ROLES.get(part.lower())
            if role:
                return role

    # 3. Symbol name fallback
    symbol = getattr(finding, "symbol", None)
    if symbol:
        return f"den Bereich um \u201e{symbol}\u201c"

    return "einen Bereich deines Projekts"


# ---------------------------------------------------------------------------
# Prompt templates (PRD F-05, F-06, F-07)
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATES: dict[str, str] = {
    "pattern_fragmentation": (
        "In meinem Projekt gibt es mehrere Stellen, die dasselbe auf "
        "unterschiedliche Art lösen — vor allem in {file_role}. "
        "Bitte vereinheitliche diese Stellen, sodass nur noch ein Muster "
        "verwendet wird. Danach sollte der Code konsistenter sein und du "
        "bessere Vorschläge machen können."
    ),
    "architecture_violation": (
        "In meinem Projekt greift {file_role} auf Bereiche zu, die "
        "eigentlich getrennt sein sollten. Bitte trenne die Zuständigkeiten "
        "sauber, sodass jede Schicht nur ihre eigene Aufgabe hat. "
        "Danach sollte das Projekt leichter erweiterbar sein."
    ),
    "mutant_duplicate": (
        "In meinem Projekt gibt es fast identische Code-Abschnitte in "
        "{file_role} mit kleinen Abweichungen. Bitte fasse diese zusammen, "
        "sodass die Logik nur einmal existiert. Danach sollten Änderungen "
        "einfacher und fehlerfreier sein."
    ),
    "explainability_deficit": (
        "In meinem Projekt ist {file_role} schwer nachvollziehbar — "
        "zu verschachtelt oder zu komplex. Bitte vereinfache die Logik, "
        "sodass man auf einen Blick versteht, was passiert. "
        "Danach sollte der Code leichter wartbar sein."
    ),
    "doc_impl_drift": (
        "Die Dokumentation in meinem Projekt passt nicht mehr zum "
        "tatsächlichen Code in {file_role}. Bitte aktualisiere die "
        "Dokumentation, sodass sie wieder stimmt. "
        "Danach sollte die Dokumentation vertrauenswürdig sein."
    ),
    "system_misalignment": (
        "Die Projektstruktur passt nicht zu dem, was {file_role} tatsächlich "
        "tut. Bitte ordne die Dateien so an, dass die Struktur die Funktion "
        "widerspiegelt. Danach sollte es einfacher sein, sich im Projekt "
        "zurechtzufinden."
    ),
    "broad_exception_monoculture": (
        "In {file_role} werden Fehler zu allgemein abgefangen. "
        "Bitte verwende spezifischere Fehlerbehandlung, sodass man erkennt, "
        "was schiefgelaufen ist. Danach sollten Fehler leichter zu finden "
        "und zu beheben sein."
    ),
    "test_polarity_deficit": (
        "Die Tests in meinem Projekt prüfen in {file_role} nur den "
        "Normalfall. Bitte ergänze Tests für Fehlerfälle und Grenzwerte. "
        "Danach sollte das Projekt robuster gegen unerwartete Situationen sein."
    ),
    "guard_clause_deficit": (
        "In {file_role} werden Eingaben nicht früh genug geprüft. "
        "Bitte füge am Anfang der Funktionen Prüfungen hinzu, die "
        "ungültige Eingaben sofort abfangen. Danach sollte der Code "
        "übersichtlicher und sicherer sein."
    ),
    "naming_contract_violation": (
        "In meinem Projekt sind Benennungen in {file_role} inkonsistent. "
        "Bitte vereinheitliche die Namensgebung, sodass gleiche Konzepte "
        "gleich benannt sind. Danach sollte der Code leichter verständlich sein."
    ),
    "bypass_accumulation": (
        "In {file_role} gibt es viele Stellen, an denen Qualitätsprüfungen "
        "übersprungen werden (z.\u202fB. TODO, FIXME, type: ignore). "
        "Bitte löse die zugrunde liegenden Probleme, sodass die Bypasses "
        "entfernt werden können. Danach sollte die Codequalität steigen."
    ),
    "exception_contract_drift": (
        "In meinem Projekt werfen verschiedene Stellen in {file_role} "
        "unterschiedliche Fehlertypen für ähnliche Situationen. "
        "Bitte vereinheitliche die Fehlerbehandlung. Danach sollte die "
        "Fehlerbehandlung konsistenter und vorhersagbarer sein."
    ),
    "cohesion_deficit": (
        "In meinem Projekt macht {file_role} zu viele verschiedene Dinge. "
        "Bitte teile die Verantwortlichkeiten auf, sodass jede Datei "
        "eine klare Aufgabe hat. Danach sollte der Code leichter zu "
        "verstehen und zu ändern sein."
    ),
    "co_change_coupling": (
        "In meinem Projekt müssen bestimmte Dateien rund um {file_role} "
        "immer zusammen geändert werden. Bitte entkopple diese "
        "Abhängigkeiten, sodass Änderungen an einer Stelle nicht immer "
        "Änderungen an anderen erfordern. Danach sollte das Projekt "
        "flexibler sein."
    ),
    "fan_out_explosion": (
        "In meinem Projekt importiert {file_role} zu viele andere Module. "
        "Bitte reduziere die Abhängigkeiten, indem du Aufgaben aufteilst "
        "oder eine Abstraktionsschicht einführst. Danach sollte der Code "
        "weniger fehleranfällig bei Änderungen sein."
    ),
    "hardcoded_secret": (
        "In meinem Projekt gibt es fest eingebaute Zugangsdaten oder "
        "Schlüssel in {file_role}. Bitte verschiebe diese in "
        "Umgebungsvariablen oder eine sichere Konfigurationsdatei. "
        "Danach sollte das Projekt sicherer sein."
    ),
    "phantom_reference": (
        "In meinem Projekt verweist {file_role} auf Funktionen oder "
        "Module, die nicht mehr existieren. Bitte entferne oder "
        "aktualisiere diese Verweise. Danach sollte der Code fehlerfrei "
        "ausführbar sein."
    ),
    # --- Report-only (fallback, less likely to appear) ---
    "temporal_volatility": (
        "In meinem Projekt werden bestimmte Dateien rund um {file_role} "
        "ungewöhnlich häufig geändert. Bitte prüfe, ob diese Dateien zu "
        "viele Aufgaben übernehmen. Danach sollte die Änderungshäufigkeit "
        "sinken."
    ),
    "ts_architecture": (
        "Der TypeScript-Code in {file_role} hat strukturelle Probleme. "
        "Bitte überarbeite die Modulstruktur. Danach sollte der Code "
        "besser organisiert sein."
    ),
    "cognitive_complexity": (
        "In {file_role} sind Funktionen zu komplex verschachtelt. "
        "Bitte vereinfache die Logik durch Aufteilen oder Extrahieren. "
        "Danach sollte der Code leichter verständlich sein."
    ),
    "circular_import": (
        "In meinem Projekt importieren sich Module rund um {file_role} "
        "gegenseitig. Bitte löse den Kreis auf, indem du gemeinsamen Code "
        "in ein eigenes Modul auslagerst. Danach sollte das Projekt "
        "ohne Import-Fehler starten."
    ),
    "dead_code_accumulation": (
        "In {file_role} gibt es ungenutzten Code. Bitte entferne nicht "
        "mehr benötigte Funktionen und Klassen. Danach sollte das Projekt "
        "übersichtlicher sein."
    ),
    "missing_authorization": (
        "In meinem Projekt fehlt möglicherweise eine Zugriffsprüfung in "
        "{file_role}. Bitte stelle sicher, dass alle Endpunkte eine "
        "Authentifizierung oder Autorisierung erfordern. Danach sollte "
        "das Projekt sicherer sein."
    ),
    "insecure_default": (
        "In {file_role} werden unsichere Standardwerte für "
        "sicherheitsrelevante Einstellungen verwendet. Bitte ändere diese "
        "auf sichere Defaults. Danach sollte das Projekt weniger "
        "angreifbar sein."
    ),
    "type_safety_bypass": (
        "In {file_role} werden Typ-Prüfungen umgangen. Bitte ersetze die "
        "Umgehungen durch korrekte Typ-Annotationen. Danach sollte der "
        "Code robuster und verständlicher sein."
    ),
}


def generate_agent_prompt(finding: Any, analysis: Any | None = None) -> str:
    """Generate a copy-paste-ready prompt for the given finding.

    The prompt uses everyday German, references files by functional role
    (not raw paths), and includes an expected-outcome sentence (PRD F-07).

    Parameters
    ----------
    finding:
        A ``Finding`` instance.
    analysis:
        Optional ``RepoAnalysis`` for extra context (currently unused).
    """
    role = file_role_description(finding)
    template = _PROMPT_TEMPLATES.get(finding.signal_type)
    if template is None:
        # Ultimate fallback for unknown signal types
        return (
            f"In meinem Projekt gibt es ein Problem in {role}. "
            "Bitte überprüfe und behebe es. "
            "Danach sollte der Code besser strukturiert sein."
        )
    return template.format(file_role=role)

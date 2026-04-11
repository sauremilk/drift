---
id: ADR-047
status: proposed
date: 2026-04-11
type: signal-design
signal_id: MAZ
supersedes:
---

# ADR-047: MAZ Security Tier — CRITICAL Severity + Rich-Output Security Block

## Kontext

Der `missing_authorization`-Signal (MAZ) erzeugt gegenwärtig alle Findings mit `Severity.HIGH`. Im Actionability Review (2026-04-11) wurde festgestellt, dass:

1. Security-Findings visuell nicht von strukturellen Findings getrennt sind — MAZ-Findings verlieren sich in der Findings-Tabelle zwischen 550+ anderen Ergebnissen.
2. Die Fix-Texte sind generisch ("Add an authorization check") ohne Import-Pfad oder A2A-Exemption-Hinweis.
3. Security-sensitive Endpunkte in Production-Kontext verdienen `Severity.CRITICAL`, nicht nur `HIGH`, was eine höhere RPZ in der FMEA rechtfertigt.

Ähnliche Signals: `heuristic_security_check` (HSC), `insecure_deserialization` (ISD).

## Entscheidung

**Was wird getan:**
1. MAZ: `Severity.HIGH` → `Severity.CRITICAL` wenn `finding_context == "production"` (sofern der Context-Resolver dieses Feld bestückt) oder bei Score ≥ 0.8. Für alle anderen Fälle bleibt `HIGH`.
2. Rich-Output: Neue Funktion `_render_security_section()` die alle Findings mit `signal_id in SECURITY_SIGNALS` (= `{"MAZ", "HSC", "ISD"}`) bündelt und **vor** der allgemeinen Findings-Tabelle in einem dedizierten Panel rendert.
3. Fix-Text-Vorlage für MAZ erweitern: `"from <auth_module> import get_current_user\n# Note: A2A agents are exempt if using service-account tokens"`.

**Was explizit nicht getan wird:**
- Kein Änderung am Score-Algorithmus von MAZ.
- Kein neues Signal; nur Severity-Mapping und Output-Rendering.
- HSC und ISD erhalten kein separates CRITICAL-Upgrade in diesem ADR (follow-up).

## Begründung

Security-Findings müssen für den Maintainer sofort identifizierbar sein ohne die Gesamtliste durchscannen zu müssen. Ein dedizierter Security-Block ist die bewährteste Methode (Pattern: `bandit`, `semgrep`). `CRITICAL` für Production-Endpunkte ohne Auth ist sachlich gerechtfertigt (CVSS ≥ 9.0 Klasse).

Alternativen verworfen: Separate Severity-Kategorie `SECURITY` (würde Severity-Enum inkompatibel machen, Breaking Change); eigenständige Security-Subcommand (unnötige Oberfläche ohne Mehrwert).

## Konsequenzen

- Maintainer sieht Security-Findings sofort beim ersten Blick auf Rich-Output.
- MAZ-Severity-Upgrade kann in CI-Pipelines zu neuen `exit 1`-Codes führen, wenn der Aufrufer auf Severity-Level filtert. Dieses Verhalten ist gewollt und wird in CHANGELOG dokumentiert.
- JSON-Output-Schema ändert sich nicht (Severity ist bereits ein Enum-Wert).

## Fixture-Plan

- TN-Fixture: `maz_a2a_public_endpoint_intentional` — öffentlicher Endpunkt mit A2A-Service-Account-Token → kein CRITICAL
- TP-Fixture: Endpunkt ohne Auth in production context → CRITICAL

## FMEA-Vorab-Eintrag

| Failure Mode | Severity | Occurrence | Detection | RPN |
|---|---|---|---|---|
| FP: A2A-Exemption-Endpunkt als CRITICAL markiert | 7 | 3 | 7 | 147 |
| FN: Production-Kontext nicht erkannt → bleibt HIGH | 4 | 5 | 6 | 120 |

## Validierungskriterium

1. `drift analyze --repo . --format rich` zeigt Security-Block vor Findings-Tabelle.
2. Im Self-Analysis: mindestens eine MAZ-Finding mit `severity == "critical"` wenn entsprechende Fixture greift.
3. `pytest tests/test_precision_recall.py` bleibt grün (kein Recall-Verlust).
4. JSON-Schema-Konformitätstest besteht.

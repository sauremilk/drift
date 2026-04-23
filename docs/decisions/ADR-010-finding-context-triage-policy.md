---
id: ADR-010
status: proposed
date: 2026-04-03
supersedes:
---

# ADR-010: Finding-Context Triage Policy fuer nicht-operative Bereiche

## Kontext

Drift kann Findings in bewusst nicht-operativen Bereichen (z. B. Fixture-Korpora,
generierter Code, Migrationen, Doku) priorisieren, obwohl diese haeufig nicht
fix-first bearbeitet werden sollen. Das verzerrt die operative Reihenfolge in
scan/fix_plan und erschwert policy-konforme Automatisierung.

## Entscheidung

Wir fuehren eine konfigurierbare finding_context-Klassifizierung ein:

- Jeder Finding-Eintrag erhaelt einen maschinenlesbaren Kontext
  (default: production, fixture, generated, migration, docs).
- Kontextzuordnung erfolgt ueber konfigurierbare Glob-Regeln mit precedence.
- Nicht-operative Kontexte werden standardmaessig aus Priorisierungsqueues
  (fix_first/fix_plan) ausgeschlossen.
- Ein explizites Opt-in erlaubt deren Einbezug in Priorisierung.
- scan/fix_plan geben Kontextzaehlung und Filterentscheidung maschinenlesbar aus.

Explizit nicht Teil dieser ADR:
- keine vollstaendige Unterdrueckung dieser Findings aus Roh-Analyseausgaben
- keine repo-spezifischen Hardcodings in Signaldetektoren

## Begründung

Diese Loesung verbessert Handlungsfaehigkeit und Prioritaetsqualitaet ohne
Signalverlust: Findings bleiben sichtbar, aber operative Reihenfolgen werden
policy-gerecht fokussiert. Gegenueber hartem Exclude bleiben Audits und explizite
Reviews weiterhin moeglich.

## Konsequenzen

- Additive Schema-Erweiterung in API/JSON-Ausgaben (finding_context + policy-Felder).
- Default-Verhalten der Priorisierung wird konservativer und operativer.
- Repositories koennen Kontexte je Pfadregel selbst ueberschreiben.
- Trade-off: leicht mehr Konfigurationsflaeche und Erklaerungsbedarf in Doku.

## Validierung

- Unit-Tests fuer Klassifizierung mit mehreren Fixture-Layouts + Generated-Layout.
- API-Tests fuer Default-Ausschluss und Opt-in in scan/fix_plan.
- Lernzyklus-Status gemaess Policy §10: unklar (zu bestaetigen nach Feldnutzung).

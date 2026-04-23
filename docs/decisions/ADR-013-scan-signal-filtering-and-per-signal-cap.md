---
id: ADR-013
status: proposed
date: 2026-04-05
supersedes:
---

# ADR-013: Scan-Filtering fuer dominante Signale und balancierte Ergebnislisten

## Kontext

Issue #173 zeigt ein Ranking- und Actionability-Problem fuer grosse Repositories:
`drift scan` kann von einem dominanten Signal (z. B. MDS) nahezu vollstaendig
gepraegt werden. Dadurch sind andere, oft handlungsrelevante Signale in den
Top-Resultaten kaum sichtbar.

## Entscheidung

Wir erweitern den agent-nativen Scan um zwei gezielte Steuerungen:

- Signal-Exclusion im Scan (`--exclude-signals`)
- Optionale per-Signal Obergrenze fuer die Rueckgabe (`--max-per-signal`)

Diese Parameter werden konsistent ueber CLI, API und MCP durchgereicht.
Die bestehende Strategieauswahl (`diverse`/`top-severity`) bleibt erhalten.

Explizit nicht Teil dieser ADR:

- keine Aenderung an Signal-Detektionsheuristiken
- keine Aenderung an Signal-Gewichten/Scoring
- keine neue Severity-Schwelle als zusaetzliches Filterkriterium

## Begruendung

Die Erweiterung verbessert die Handlungsfaehigkeit direkt:

- Agenten koennen bekannte Rauschsignale gezielt ausblenden.
- Ergebnislisten bleiben fokussiert und token-effizient.
- Die Aenderung ist klein, rueckwaertskompatibel und greift nicht in die
  Signal-Detektion ein.

## Konsequenzen

- Zusetzliche CLI/API-Parameter erhoehen leicht die Bedienoberflaeche.
- Diagnostics koennen nun auch Omission durch per-Signal Cap ausweisen.
- Bestehende Workflows ohne neue Flags bleiben unveraendert.

## Validierung

- CLI-Regressionstests fuer Option-Weitergabe (`scan`)
- API-Tests fuer per-Signal Cap und Exclusion-Weitergabe
- Policy §10 Lernzyklus-Status: unklar (Praxisfeedback aus grossen Repos folgt)

---
applyTo: "**"
description: "Drift Policy — Bindende Arbeitsregeln für alle Dateien. MUSS gelesen werden bevor Änderungen an Drift-Code, Analyselogik, Ergebnisformaten oder Features vorgenommen werden."
---

# Drift — Policy (bindend für alle Dateioperationen)

Vollständige Policy: `POLICY.md` im Workspace-Root.
Kurzfassung der Kern-Verbote und Anforderungen:

## PFLICHT-GATE: Zulässigkeitsprüfung — immer zuerst ausführen und ausgeben

Vor jeder Umsetzung dieses Format sichtbar ausgeben:

```
### Drift Policy Gate
- Aufgabe: [Kurzbeschreibung in einem Satz]
- Zulassungskriterium erfüllt: [JA / NEIN] → [Unsicherheit / Signal / Glaubwürdigkeit / Handlungsfähigkeit / Trend / Einführbarkeit]
- Ausschlusskriterium ausgelöst: [JA / NEIN] → [falls JA: welches]
- Roadmap-Phase: [1 / 2 / 3 / 4] — blockiert durch höhere Phase: [JA / NEIN]
- Entscheidung: [ZULÄSSIG / ABBRUCH]
- Begründung: [ein Satz]
```

Bei **ABBRUCH**: keine Umsetzung, stattdessen Erklärung + Gegenvorschlag.
Das Gate darf **niemals übersprungen** werden.

---

## Vor jeder Änderung prüfen

**Ist die Aufgabe zulässig?** Sie muss mindestens eines erfüllen:
- reduziert eine zentrale Unsicherheit
- verbessert die Signalqualität oder Glaubwürdigkeit
- erhöht die Handlungsfähigkeit
- verbessert Trendfähigkeit oder Einführbarkeit

**Ist die Aufgabe unzulässig?** Sofort abbrechen, wenn sie ausschließlich erzeugt:
- mehr Ausgabe ohne Erkenntniswert
- mehr Komplexität ohne klaren Nutzen
- ein Feature, dessen Beitrag nicht klar benennbar ist

## Pflicht bei Code-Änderungen an Analyseergebnissen

Jedes Ergebnis/Befund benötigt zwingend:
1. technische Nachvollziehbarkeit
2. Reproduzierbarkeit  
3. eindeutige Ursachenzuordnung
4. nachvollziehbare Begründung
5. erkennbare nächste Maßnahme

Fehlt eines dieser fünf Elemente → Änderung ist **unzulässig**.

## Prioritätsbindung

Reihenfolge ist nicht verhandelbar:
`Glaubwürdigkeit > Signalpräzision > Verständlichkeit > FP/FN-Reduktion > Einführbarkeit > Trend > Features`

---
name: guard-src-drift-calibration
description: "Drift-generierter Guard fuer `src/drift/calibration`. Aktiv bei Signalen: EDS. Konfidenz: 0.68. Verwende diesen Skill wenn du Aenderungen an `src/drift/calibration` planst oder wiederholte Drift-Findings (EDS) fuer dieses Modul bearbeitest."
argument-hint: "Beschreibe was am Kalibrierungs-Zyklus geaendert wird — Schwellenwert-Logik, Feedback-Verarbeitung oder Calibration-Loop-Steuerung."
---

# Guard: `src/drift/calibration`

`src/drift/calibration` implementiert den automatischen Kalibrierungs-Zyklus: Feedback einlesen → Schwellenwerte anpassen → Drift-Konfiguration aktualisieren. EDS tritt auf weil die Kalibrierungslogik mehrere interdependente Zustandsuebergaenge abbildet, die schwer zu trennen sind.

**Konfidenz: 0.68** — moderates EDS-Risiko; der Kalibrierungszyklus ist komplex, aber gut abgegrenzt.

## When To Use

- Du aenderst wie Nutzer-Feedback in Schwellenwert-Anpassungen uebersetzt wird
- Du veraenderst den Kalibrierungs-Loop in `ops_calibration_cycle.py`
- Du aenderst die Logik in `src/drift/calibration/`-Modulen
- Drift meldet EDS fuer eine Datei in `src/drift/calibration/`

## Warum EDS hier entsteht

Der Kalibrierungs-Zyklus hat inhaerent mehrere Schritte die aufeinander aufbauen:
1. Feedback-Events lesen
2. Signal-Thresholds berechnen
3. Threshold-Aenderungen validieren
4. `drift.yaml` oder Konfiguration schreiben

EDS entsteht wenn diese Schritte ineinander verschraenkt werden statt sequentiell zu bleiben. Ein Schritt darf den Zustand eines anderen Schritts nicht modifizieren.

## Core Rules

1. **Kalibrierungs-Schritte sind sequenziell, nicht verschraenkt** — jede Phase des Kalibrierungs-Zyklus (lesen, berechnen, validieren, schreiben) ist eine eigenstaendige Funktion. Kein Schritt greift auf den internen Zustand eines anderen zu.

2. **Dry-Run immer moeglich** — jede Aenderung an der Kalibrierungslogik muss mit `--dry-run` testbar sein ohne Seiteneffekte auf `drift.yaml`. Die `--dry-run`-Flag ist kein optionales Feature.

3. **Feedback-Persistenz ist read-only fuer die Calibration-Logik** — Kalibrierungsmodule lesen Feedback-Events, schreiben sie aber nie. Das Schreiben von Feedback ist Aufgabe von `outcome_tracker.py`.

4. **Threshold-Aenderungen durch ADR absichern** — signifikante Threshold-Aenderungen (>10% Abweichung) erfordern einen ADR-Eintrag. Kalibrierungs-Code der automatisch grosse Anpassungen vornimmt, muss dies loggen.

5. **Keine neuen EDS-Findings durch Kalibrierungs-Metriken** — Kalibrierungs-Code darf keine eigenen Qualitaetsmetriken berechnen, die redundant zu `scoring/` sind.

## Arbeitsablauf

```bash
# Kalibrierungs-Zyklus im Dry-Run testen
python scripts/ops_calibration_cycle.py --skip-analyze

# Mit vollem Analyze
python scripts/ops_calibration_cycle.py

# Mit Anwenden
python scripts/ops_calibration_cycle.py --apply
```

## Review Checklist

- [ ] Kalibrierungs-Schritte bleiben sequenziell und eigenstaendig
- [ ] `--dry-run`-Modus funktioniert ohne Seiteneffekte
- [ ] Kein Feedback-Schreiben in Kalibrierungs-Modulen
- [ ] Grosse Threshold-Aenderungen werden geloggt
- [ ] `drift nudge` zeigt `safe_to_commit: true`
- [ ] Keine neuen EDS-Findings

## References

- [scripts/ops_calibration_cycle.py](../../../scripts/ops_calibration_cycle.py) — Kalibrierungs-Loop
- [src/drift/outcome_tracker.py](../../../src/drift/outcome_tracker.py) — Feedback-Persistenz
- [DEVELOPER.md](../../DEVELOPER.md)

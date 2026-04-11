---
applyTo: "**"
description: "Drift Quality Workflow — Verbindlicher Dual-Agent-Qualitätsstandard für alle nicht-trivialen Änderungen. MUSS vor Implementierung, Review und Merge gelesen werden."
---

# Drift Quality Workflow — Verbindlicher Arbeitsstandard

Dieser Standard gilt workspace-weit für alle nicht-trivialen Änderungen an Code, Architektur, Tests, Refactorings und Features. Er ist kein Vorschlag — er ist bindend.

---

## Geltungsbereich

**Dieser Workflow ist Pflicht bei:**
- neuen Features
- Refactorings
- Bugfixes mit nicht-trivialem Impact
- Architekturänderungen
- Änderungen an Tests oder CI-relevantem Verhalten
- Änderungen an Prompt-, Agenten- oder Automationslogik

**Dieser Workflow kann reduziert werden bei:**
- kleinen Textkorrekturen
- harmlosen Renames ohne Seiteneffekte
- rein mechanischen Änderungen mit nachweislich geringem Risiko

Zweifel → voller Workflow.

---

## Verbindlicher Standardprozess (7 Stufen)

### Stufe 1 — Dual-Agent-Implementierung

Jede relevante Aufgabe wird mit zwei Rollen bearbeitet:

- **Implementierer-Rolle:** setzt die Änderung um
- **Reviewer-Rolle (adversarial):** sucht aktiv nach Bugs, Logiklücken, Spezifikationsverletzungen, riskanten Annahmen, Regressionen und fehlenden Tests

Die Reviewer-Rolle nimmt gezielt eine Gegenposition ein. Ziel ist nicht Bestätigung, sondern Schwachstellenfindung.

### Stufe 2 — Iterativer Review-Loop

Implementierung und adversarialer Review laufen in Schleifen, bis die Lösung:
- fachlich konsistent ist
- technisch plausibel ist
- hinreichend robust ist

Kein Verlassen dieser Schleife ohne expliziten „Bereit"-Status.

### Stufe 3 — PR-/Diff-Denkweise

Jede Änderung ist so zu behandeln, als würde sie in einen Pull Request überführt:
- Änderungen müssen nachvollziehbar sein
- Änderungen müssen begründbar sein
- Änderungen müssen reviewbar strukturiert sein

Keine „quick hacks" ohne Begründungsstruktur.

### Stufe 4 — BugBot-Phase nach pushbarem Stand

Nach jedem pushbaren Zwischenstand wird ein separater BugBot-Review-Schritt ausgeführt.

**Strukturierte Review-Checkliste verwenden:** Der Reviewer arbeitet die Checkliste unter `.github/prompts/_partials/review-checkliste.md` Punkt für Punkt ab und dokumentiert pro Punkt Ja / Nein / N/A mit Kurzbegründung. Kein Punkt darf übersprungen werden.

**Dieser Review bewertet isoliert und streng:**
- Korrektheit der Änderung
- Risiko und Edge Cases
- Testabdeckung (vorhanden / fehlend / unzureichend)
- Codequalität
- Nebenwirkungen und Regressionspotenzial

Das BugBot-Review ist kein Formalismus — es ist ein adversarialer Angriff auf die Änderung.

### Stufe 5 — Automatische Nachbesserung

Findings aus dem Review werden nicht als Kommentare stehengelassen.
Sie werden automatisch in konkrete Fixes übersetzt und abgearbeitet.

Verhalten:
- Finding → konkreter Änderungsvorschlag → Umsetzung → erneutes Review
- Kein Stehenbleiben beim Review

### Stufe 6 — Grün-vor-Merge-Regel

„Grün" bedeutet **alle** der folgenden Bedingungen:
- keine offenen kritischen Findings
- keine unbehandelten High-Risk-Kommentare
- wesentliche Checks bestanden oder plausibel abgesichert
- bekannte Restrisiken explizit benannt (nicht verschwiegen)

Jede Änderung endet mit einem expliziten Freigabestatus:
- `❌ NICHT BEREIT` — offene kritische Issues
- `⚠️ BEREIT ZUR MENSCHLICHEN PRÜFUNG` — Checks grün, aber Risiken sichtbar
- `✅ BEREIT ZUM MERGE` — vollständig grün, alle Gates erfüllt

### Stufe 7 — Menschliches Freigabe-Gate

Der finale Merge oder Abschluss einer Änderung erfolgt **nicht autonom**.

Ein Mensch trifft die letzte Entscheidung.

**Lokaler Final-Check ist verpflichtend wenn:**
- Laufzeitverhalten relevant ist
- UX oder CLI-Interaktion betroffen ist
- Integrationen oder I/O verändert wurden
- Build-, Test- oder Packaging-Pfade betroffen sind
- die Änderung schwer aus statischer Analyse allein beurteilbar ist

**Lokaler Final-Check kann entfallen wenn:**
- die Änderung klar isoliert und risikoarm ist
- vollständig durch Review und Checks abgedeckt
- explizit als trivial klassifiziert

---

## Operative Verhaltensregeln für alle Agenten

1. **Kein Single-Agent-Modus** bei fachlich oder technisch relevanten Änderungen
2. **Mindestens eine explizite Gegenprüfungsperspektive** zu jeder relevanten Änderung
3. **Reviews sind adversariale Angriffe** auf Robustheit — keine Formalität
4. **Findings → konkrete nächste Schritte** — keine bloßen Kommentare
5. **Unsicherheit, Trade-offs, fehlende Validierung, hohes Risiko** werden sichtbar an den Menschen eskaliert
6. **Freigabestatus vor Abschluss** immer explizit ausgeben

### Batch-Repair-Ausnahme (ADR-020)

Beim **Batch-Fix-Modus** (mehrere gleichartige Findings in einem Zug) darf der Review-Loop vereinfacht werden:
- Wenn `batch_eligible=true` in der fix_plan-Antwort gesetzt ist, können alle `affected_files_for_pattern` mit dem gleichen Fix-Template bearbeitet werden, bevor ein `drift_diff` zur Verifikation läuft.
- Der adversariale Review reduziert sich auf Stichproben (≥ 1 Datei pro Batch), nicht auf jede Einzeldatei.
- Die übrigen Qualitätsregeln (Stufen 5–7) gelten unverändert.

---

## Gesamtfluss (Referenz)

```
Implementierung
    ↓
adversarialer Gegenreview (Reviewer-Rolle)
    ↓
Iterativer Fix-Loop (bis konsistent & robust)
    ↓
pushbarer Zustand → BugBot-artiges PR-Review
    ↓
automatische Fixes aus Review-Findings
    ↓
grüne Checks + expliziter Freigabestatus
    ↓
menschliche Freigabe (Human-in-the-Loop-Gate)
    ↓
Merge / Abschluss
```

---

## Verhältnis zur Drift Policy

Dieser Workflow **ergänzt** die Drift Policy (`POLICY.md`). Er ersetzt sie nicht.
Das PFLICHT-GATE aus der Drift Policy (`drift-policy.instructions.md`) läuft **vor** diesem Workflow.
Bei Widerspruch gilt: Drift Policy hat Vorrang.

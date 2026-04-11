# Baseline

Die Baseline ist das Werkzeug für inkrementelle Adoption: Sie erlaubt, drift in einem Bestandsprojekt einzuführen, ohne sofort von einem Backlog vorhandener Findings erschlagen zu werden.

---

## Was ist die `.drift-baseline.json`?

Die `.drift-baseline.json` ist ein Fingerprint-Snapshot aller Findings, die zu einem bestimmten Zeitpunkt im Repository bekannt waren. Jeder Befund wird durch seine Signal-ID, den Dateipfad, die Zeilennummer und den Titel eindeutig identifiziert — über einen SHA-256-basierten Fingerprint.

Dateistruktur (Beispiel):

```json
// Beispiel-Output
{
  "baseline_version": 1,
  "drift_version": "2.5.1",
  "created_at": "2026-04-10T09:15:00+00:00",
  "drift_score": 0.38,
  "finding_count": 12,
  "findings": [
    {
      "fingerprint": "<fingerprint>",
      "signal": "pattern_fragmentation",
      "severity": "high",
      "file": "src/api/handlers.py",
      "start_line": 42,
      "title": "Error handling fragmented (3 variants)"
    }
  ]
}
```

Der Fingerprint ist stabil gegenüber Whitespace-Änderungen und kleineren Reformatierungen, solange Signal-ID, Dateipfad, Zeilennummer und Titel unverändert bleiben.

---

## Wann wird eine Baseline erstellt? Wann veraltet sie?

### Erstellt mit `drift baseline save`

```bash
drift baseline save                      # Speichert nach .drift-baseline.json
drift baseline save --output custom.json # Eigener Pfad
drift baseline save --since 60           # Nur 60 Tage Git-History
```

Die Baseline enthält alle Findings, die drift in der aktuellen Analyse gefunden hat. Wenn du `drift check --baseline .drift-baseline.json` verwendest, werden alle in der Baseline known Findings unterdrückt — nur neue Findings seit dem Baseline-Zeitpunkt erscheinen.

### Veraltet bei Strukturänderungen

Eine Baseline veraltet graduell, wenn:

- **Die Zeilen eines Findings signifikant verschoben werden** — der Fingerprint enthält `start_line`, deshalb führt umfangreiches Refactoring zu neuen Fingerprints
- **Findings behoben werden** — die Baseline enthält resolved Findings; sie erscheinen nicht mehr in der aktuellen Analyse, was aber keine Warnung erzeugt
- **Neue Findings hinzukommen** — die Baseline kennt sie nicht, sie erscheinen ungefilltert im diff-Output

> Eine veraltete Baseline schadet nicht — sie führt allenfalls dazu, dass bereits behobene Findings als unbekannt eingestuft werden (unproblematisch) oder neue Findings korrekt angezeigt werden.

---

## Manuell refreshen vs. automatisch

### Manuell refreshen

Empfohlen, wenn:
- Ein größeres Refactoring abgeschlossen ist und die bisherigen Findings als "akzeptiert" gelten
- Das Team einen Meilenstein abgeschlossen hat und von einer neuen Basis aus weiter arbeiten möchte
- Eine Release-Version eingefroren werden soll

```bash
drift baseline save
git add .drift-baseline.json
git commit -m "chore: update drift baseline"
```

### Automatisch über CI

Im GitHub Actions Workflow kannst du die Baseline automatisch bei Merges auf `main` aktualisieren:

```yaml
# Beispiel-Output: Baseline-Update-Step
- name: Update baseline on main
  if: github.ref == 'refs/heads/main'
  run: |
    drift baseline save
    git config user.email "ci@example.com"
    git config user.name "CI Bot"
    git add .drift-baseline.json
    git diff --cached --quiet || git commit -m "chore: drift baseline update"
    git push
```

Für die meisten Teams ist ein manueller Refresh der bessere Ansatz: Er dokumentiert explizit, welche Findings bewusst akzeptiert wurden.

---

## Was passiert bei einem Baseline-Reset?

Ein Reset bedeutet, die Baseline zu löschen oder durch eine neue zu ersetzen. Folgen:

1. **Alle bisherigen Suppressionen werden aufgehoben.** Beim nächsten `drift check --baseline` erscheinen alle Findings, auch solche, die zuvor als known galten.

2. **Ein Neustart bei null ist möglich** — nützlich nach einem umfassenden Refactoring oder wenn das Repository substanziell bereinigt wurde.

3. **Inkrementalität geht verloren** — ohne Baseline wird jedes Finding als neu behandelt.

**Baseline-Vergleich anzeigen:**

```bash
drift baseline diff
```

Zeigt, welche Findings seit dem letzten Baseline-Save neu hinzugekommen sind und welche nicht mehr auftreten.

```
# Beispiel-Output
  3 new findings since baseline:
    ⚠ AVS: Architecture violation in src/payments/service.py
    ⚠ MDS: Mutant duplicate in src/users/handler.py
    ⚠ PFS: Pattern fragmentation in src/api/validators.py

  2 findings resolved:
    ✓ BEM: Broad exception monoculture in src/legacy/utils.py
    ✓ TPD: Test polarity deficit in tests/test_auth.py

  baseline_score: 0.38  →  current_score: 0.44  (Δ +0.06)
```

---

## Nächste Schritte

- [**scoring.md**](scoring.md) — Wie der Drift-Score berechnet wird und was Schwellwerte bedeuten
- [**../guides/ci-integration.md**](../guides/ci-integration.md) — Baseline in CI-Workflows einsetzen
- [**../guides/quickstart.md**](../guides/quickstart.md) — Erste Schritte: Installation, scan, check

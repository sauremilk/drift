# Review-Checkliste (Shared Reference)

> **Single Source of Truth** — Alle adversarialen Reviews verwenden diese Checkliste.
> Die Checkliste ersetzt keine Eigenleistung des Reviewers, sie strukturiert sie.

## Anwendung

Der Reviewer arbeitet die Checkliste Punkt für Punkt ab und dokumentiert pro Punkt:
- **Ja** / **Nein** / **N/A** (mit Kurzbegründung bei Nein oder N/A)

Kein Punkt darf übersprungen werden. Bei Unsicherheit: `Nein` mit Begründung.

---

## 1. Policy-Konformität

- [ ] **Policy-Gate korrekt?** — Wurde das PFLICHT-GATE sichtbar ausgegeben, und ist die Begründung plausibel (nicht rituell)?
- [ ] **Zulassungskriterium nachvollziehbar?** — Ist das benannte Kriterium (Unsicherheit / Signal / Glaubwürdigkeit / Handlungsfähigkeit / Trend / Einführbarkeit) tatsächlich adressiert?
- [ ] **Ausschlusskriterium geprüft?** — Erzeugt die Änderung ausschließlich mehr Ausgabe/Komplexität/Features ohne benennbaren Nutzen?
- [ ] **Priorisierung eingehalten?** — Verdrängt die Änderung eine höherpriorisierte Aufgabe (§6)?

## 2. Scope und Boundaries

- [ ] **Scope eingehalten?** — Wurden nur Dateien geändert, die zur Aufgabe gehören?
- [ ] **Out-of-Scope unberührt?** — Wurden keine Dateien modifiziert, die explizit oder implizit außerhalb des Auftrags liegen?
- [ ] **Keine ungefragt hinzugefügten Features?** — Enthält die Änderung nur das Angefragte, keine "Verbesserungen" oder Refactorings als Beifang?

## 3. Architektur und ADR-Pflicht

- [ ] **ADR erforderlich?** — Betrifft die Änderung Signale, Scoring, Output oder Architektur-Boundaries? Falls ja: ADR unter `decisions/` vorhanden (Status `proposed` reicht)?
- [ ] **Architektur-Layer korrekt?** — Respektiert die Änderung den Datenfluss `ingestion → signals → scoring → output`?
- [ ] **Keine unzulässigen Layer-Übergriffe?** — Greift kein Modul auf eine Schicht zu, zu der es laut Architektur keinen Zugang haben sollte?

## 4. Audit-Pflicht (Policy §18)

- [ ] **Betrifft die Änderung `signals/`, `ingestion/` oder `output/`?** — Falls nein: N/A.
- [ ] **Audit-Artefakte aktualisiert?** — Wurde mindestens das richtige Artefakt inhaltlich (nicht nur kosmetisch) aktualisiert?
  - Signal-Änderung → `fmea_matrix.md` + `fault_trees.md` + `risk_register.md`
  - Input/Output-Pfad → `stride_threat_model.md` + `risk_register.md`
  - Precision/Recall Δ > 5% → `fmea_matrix.md` (RPNs) + `risk_register.md`
- [ ] **Alle vier Audit-Artefakte existieren noch?** — Kein Löschrisiko?

## 5. Befund-Qualität (§13)

Nur relevant, wenn die Änderung Analyseergebnisse / Befunde betrifft.

- [ ] **Technische Nachvollziehbarkeit?** — Kann ein Dritter den Befund anhand des Codes rekonstruieren?
- [ ] **Reproduzierbarkeit?** — Liefert dieselbe Eingabe denselben Befund?
- [ ] **Eindeutige Ursachenzuordnung?** — Ist klar, welche Code-Stelle den Befund auslöst?
- [ ] **Nachvollziehbare Begründung?** — Steht eine Erklärung, warum dies ein Problem ist?
- [ ] **Erkennbare nächste Maßnahme?** — Weiß der Empfänger, was zu tun ist?

## 6. Code-Qualität

- [ ] **Docstrings vorhanden?** — Jede neue öffentliche Funktion unter `src/drift/` hat einen Docstring?
- [ ] **Keine offensichtlichen Bugs?** — Edge Cases, Off-by-One, Null-Handling geprüft?
- [ ] **Keine Sicherheitslücken?** — OWASP Top 10 beachtet (Path Traversal, Injection, etc.)?
- [ ] **Typisierung konsistent?** — mypy-konform, keine unannotierten öffentlichen Signaturen?

## 7. Tests

- [ ] **Tests vorhanden?** — Gibt es Tests für das neue/geänderte Verhalten?
- [ ] **Regressionstests?** — Bestehendes Verhalten durch Tests abgesichert?
- [ ] **Edge Cases abgedeckt?** — Leere Eingaben, Grenzwerte, Fehlerpfade?
- [ ] **Keine duplizierten Testnamen?** — Kein `def test_...`-Duplikat im selben Modul?

## 8. Commit und Gates

- [ ] **Conventional Commit korrekt?** — `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:` passend gewählt?
- [ ] **CHANGELOG aktualisiert?** — Bei `feat:` oder `fix:`: Eintrag in `CHANGELOG.md` vorhanden?
- [ ] **Feature-Evidence vorhanden?** — Bei `feat:`: Tests + `benchmark_results/vX.Y.Z_*.json` + `docs/STUDY.md`?
- [ ] **Lockfile synchron?** — Bei `pyproject.toml`-Änderung: `uv.lock` aktualisiert?

## 9. Gesamtbewertung

- [ ] **Bekannte Restrisiken benannt?** — Sind Trade-offs oder offene Punkte explizit dokumentiert (nicht verschwiegen)?
- [ ] **Freigabestatus bestimmt:**
  - `❌ NICHT BEREIT` — offene kritische Issues
  - `⚠️ BEREIT ZUR MENSCHLICHEN PRÜFUNG` — Checks grün, aber Risiken sichtbar
  - `✅ BEREIT ZUM MERGE` — vollständig grün, alle Gates erfüllt

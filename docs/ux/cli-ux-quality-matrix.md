# Drift CLI-UX Quality Matrix

**Stand:** 2026-04-18
**Scope:** Bestehende Terminal-Erfahrung (Rich-Output, Onboarding-Wizard, alle Subcommands)
**Methode:** Heuristik-Review (statische Analyse der CLI-Ausgaben; kein User-Test)
**Ziel:** Qualitätslücken lokalisieren, Hero-Workflow ableiten, nächste Aktionen priorisieren

---

## 1. Die 7 Kernreisen

| # | Reise | Einstiegskommando | Zielpunkt |
|---|-------|-------------------|-----------|
| J1 | **Erststart & Onboarding** | `drift setup` / `drift init` | Erster `drift status` mit verstandenem Ergebnis |
| J2 | **Tägliche Orientierung** | `drift status` | Entscheidung: handeln oder nichts tun |
| J3 | **Tiefen-Scan & Priorisierung** | `drift analyze` | 1–3 Findings ausgewählt, die angegangen werden |
| J4 | **Fix-Workflow** | Finding aus Scan | `drift status` zeigt Verbesserung |
| J5 | **Baseline & Trend** | `drift analyze --update-baseline` | `drift trend` zeigt verstandene Richtung |
| J6 | **CI-Gate** | `drift check` in CI | Exit-Code-Bedeutung klar, Violation behebbar |
| J7 | **Agent-Briefing** | `drift brief` | Output im AI-Prompt, Schutzwirkung messbar |

---

## 2. Bewertungsdimensionen (0–5)

| Kürzel | Dimension | Score 0 | Score 5 |
|--------|-----------|---------|---------|
| **K** | **Klarheit** | Kein Orientierungspunkt | Sofortverständnis ohne Docs |
| **R** | **Reibung** | Viele Flags/Loops nötig | Ziel in ≤2 Aktionen erreichbar |
| **Ko** | **Konsistenz** | Widersprüchliche Ausgaben/Begriffe | Einheitlich über alle Commands |
| **F** | **Feedback** | System-Reaktion nicht sichtbar | Echtzeit-Status + klares Ergebnis |
| **E** | **Fehlerbehandlung** | Crash/Stacktrace ohne Kontext | Erklärender Text + nächster Schritt |
| **G** | **Geschwindigkeit** | >30s, kein Fortschritt sichtbar | Sofortreaktion oder Spinner mit ETA |
| **V** | **Visueller Fokus** | Alles gleich gewichtet, Rauschen | 1 Hauptaussage pro Screen, klare Hierarchie |

---

## 3. Ist-Score-Matrix (Heuristik-Review)

> Basis: Statische Analyse der Quellcode-Ausgaben in `src/drift/commands/`.
> ⚠️ Scores ohne User-Tests; müssen nach Feldtest angepasst werden.

| Reise | K | R | Ko | F | E | G | V | **Ø** |
|-------|---|---|----|---|---|---|---|-------|
| J1 Erststart & Onboarding | 3 | 4 | 3 | 3 | 3 | 5 | 3 | **3.4** |
| J2 Tägliche Orientierung | 4 | 5 | 4 | 4 | 3 | 4 | 4 | **4.0** |
| J3 Tiefen-Scan & Priorisierung | 4 | 3 | 4 | 4 | 4 | 3 | 3 | **3.6** |
| J4 Fix-Workflow | 3 | 3 | 4 | 3 | 4 | 4 | 3 | **3.3** |
| J5 Baseline & Trend | 3 | 4 | 3 | 3 | 3 | 3 | 3 | **3.0** |
| J6 CI-Gate | 4 | 4 | 4 | 4 | 4 | 3 | 3 | **3.7** |
| J7 Agent-Briefing | 5 | 4 | 4 | 4 | 4 | 4 | 5 | **4.3** |

### Score-Begründungen

**J1 — Erststart & Onboarding (Ø 3.4)**

- **K=3:** 3 Fragen mit klaren Optionen; aber `drift setup` ist seit v2.9 deprecated zugunsten `drift init --interactive` — zwei konkurrierende Einstiegspunkte verwirren Erstnutzer.
- **R=4:** Drei Fragen, auto-locale, schreibt `drift.yaml`, nennt nächsten Schritt. Kleines Hindernis: Deprecation-Warnung erscheint *nach* der Wizard-Interaktion.
- **Ko=3:** Zwei Wege (setup / init) führen zum gleichen Ziel — Docs und README müssen diesen Dualismus sauber auflösen.
- **F=3:** `✓ drift.yaml erstellt` + nächster Schritt werden gezeigt; kein Spinner während Dateierstellung; Overwrite-Bestätigung vorhanden.
- **E=3:** Graceful overwrite-Prompt (gelb). Deprecation-Warnung kommt erst nach Abschluss.
- **G=5:** Sofort, keine Analyse.
- **V=3:** Plaintext-Menü ohne Panel-Hierarchie; verglichen mit `drift brief` visuell unfertig.

**J2 — Tägliche Orientierung (Ø 4.0)**

- **K=4:** Emoji-Ampel, Plain-English-Headline, Top-3-Findings mit copy-paste AI-Prompts. Sehr klar.
- **R=5:** `drift status` — ein Befehl, kein Flag nötig.
- **Ko=4:** Identische Farben und Severity-Labels wie `drift analyze`.
- **F=4:** Spinner (`"Analyzing…"`) während der Analyse; klares Ergebnis-Display.
- **E=3:** Profile-Fallback auf `"vibe-coding"` ist still — keine explizite Meldung für den User. Kalibrierungshinweis ist `dim` und leicht zu übersehen.
- **G=4:** Spinner vorhanden, aber kein ETA.
- **V=4:** Gute Hierarchie: Emoji + Headline + Score + Top-3 + AI-Prompt + Next-Step. Kalibrierungshinweis in `dim` kann in langen Outputs untergehen.

**J3 — Tiefen-Scan & Priorisierung (Ø 3.6)**

- **K=4:** Rich-Tabellen mit Severity, Location, Farben. Mehrere Output-Formate gut unterstützt. Risiko: Viele Format-Optionen (json, sarif, markdown, csv, llm, ci, gate) erzeugen Entscheidungslähmung.
- **R=3:** Funktioniert mit Defaults; viele Flags (`--format`, `--fail-on`, `--exit-zero`, `--show-suppressed`) erzeugen mentale Last für Erstnutzer.
- **Ko=4:** Konsistent mit `drift status`, gleiche Severity-Farben.
- **F=4:** Rich-Fortschrittsbalken + automatischer Wechsel zu JSON-Lines in CI.
- **E=4:** Roter Fail-Text mit Threshold, grüner Pass-Text. Exit-Codes dokumentiert.
- **G=3:** ~30s für große Repos; Fortschrittsbalken hilft, aber kein ETA pro Phase.
- **V=3:** Viele Findings können überwältigen; Top-N-Filter existiert, aber nicht als explizite Default-Empfehlung sichtbar.

**J4 — Fix-Workflow (Ø 3.3)**

- **K=3:** `drift fix-plan` zeigt Tasks; aber der Loop "Fix anwenden → verifizieren" ist nicht innerhalb des Tools geführt — User muss selbst schlussfolgern.
- **R=3:** Separate Kommandos: `fix-plan` → manueller Fix → `status`. Kein integrierter Feedback-Zyklus.
- **Ko=4:** Konsistente Rich-Tabellen, gleiche Severity-Systematik.
- **F=3:** Nach manuellem Fix kein "du bist besser geworden"-Signal ohne erneuten `drift status`.
- **E=4:** Mutual-Exclusivity-Fehler sind klare CLI-UsageErrors. Dismiss/Reset gut dokumentiert.
- **G=4:** `fix-plan` ist schnell; JSON-Progress zu stderr.
- **V=3:** Fix-Plan-Tabelle ist gut, aber kein visueller "nächster Schritt"-Flow.

**J5 — Baseline & Trend (Ø 3.0)**

- **K=3:** "Baseline" als Konzept ist Erstnutzern oft unklar (wo gespeichert? was bedeutet "update"?).
- **R=4:** `--update-baseline` auf `analyze`, dann `drift trend` — zwei Kommandos, beide klar.
- **Ko=3:** Baseline-Dateipfad wird in normalem Output nicht angezeigt. `drift trend`-Format unterscheidet sich von `status`/`analyze`.
- **F=3:** Nach `--update-baseline` ist keine explizite Bestätigung "Baseline gespeichert unter X" im Quellcode erkennbar.
- **E=3:** Verhalten von `drift trend` ohne vorhandene Baseline ist unklar (leerer Graph?).
- **G=3:** `analyze` dauert ~30s; `trend` selbst ist schnell.
- **V=3:** Trend-Visualisierung nicht im Detail geprüft; vermutlich ASCII-Diagramm ohne starke visuelle Hierarchie.

**J6 — CI-Gate (Ø 3.7)**

- **K=4:** `drift check` ist klar (Exit 1 bei Violations). Exit-Code-Semantik dokumentiert. Roter/grüner Gate-Text.
- **R=4:** Einzelner Befehl, integriert über `--fail-on`. SARIF-Output für GitHub Actions.
- **Ko=4:** Gleiche Severity-Systematik wie analyze/status.
- **F=4:** JSON-Lines-Progress für CI (non-TTY), klare Pass/Fail-Ausgabe.
- **E=4:** Roter Fail-Text mit konkretem Threshold, Exit-Code 1.
- **G=3:** Vollständige Analyse (~30s); kein Caching in CI ohne vorheriges Baseline-Setup.
- **V=3:** In CI degradiert Rich-Output zu Plaintext; SARIF-Annotations erscheinen nur mit GitHub-Actions-Konfiguration.

**J7 — Agent-Briefing (Ø 4.3)**

- **K=5:** Innovativster Output: Panels + Guardrails mit copy-to-agent-Format, visueller Risk-Bar, Structural-Landscape-Tabelle, expliziter Follow-up-Hinweis.
- **R=4:** `drift brief` funktioniert out-of-the-box; `--scope` für Feingranularität optional.
- **Ko=4:** Konsistente Severity-Farben; Risk-Bar-Format (`■■□□`) ist command-spezifisch.
- **F=4:** JSON-Lines-Progress; saubere Panel-Ausgabe; "structurally healthy"-Meldung bei clean.
- **E=4:** BLOCK-Level geht auf Exit 1; LOW/MEDIUM/HIGH-Distinktionen gut repräsentiert.
- **G=4:** JSON-Lines-Progress; typischerweise schneller als voller Analyze-Lauf.
- **V=5:** Best-in-class: Panels mit klaren Borders, Risk-Bar, nummerierte Guardrails, Structural-Landscape-Tabelle. Hero-Qualität.

---

## 4. Gesamtbild: Stärken und Lücken

### Stärken (≥4 in Dimension)

| Stärke | Beleg |
|--------|-------|
| Reibungsarme Tages-Loop | J2 (R=5): `drift status` ohne Flags |
| Best-in-class Brief-Output | J7 (K=5, V=5): Panels, Risk-Bar, copy-to-agent |
| Robuste CI-Integration | J6: JSON-Lines, Exit-Codes, SARIF |
| Konsistente Severity-Systematik | Alle Reisen (Ko≥3): gleiche Farben/Labels |
| Echtzeit-Feedback in Scan | J3, J6 (F=4): Rich-Progressbar + JSON-Lines |

### Lücken (≤3 in Dimension)

| # | Lücke | Betroffene Reisen | Wichtigste Dimension |
|---|-------|-------------------|----------------------|
| L1 | Zwei konkurrierende Onboarding-Pfade (`setup` deprecated, `init` neu) | J1 | Ko=3, K=3 |
| L2 | Fix-Workflow ohne integriertes Verifikations-Feedback | J4 | F=3, R=3 |
| L3 | Baseline-Konzept nicht selbsterklärend; fehlende Update-Bestätigung | J5 | K=3, F=3 |
| L4 | Kein ETA in langen Scan-Phasen | J3, J5, J6 | G=3 |
| L5 | Silent profile-fallback, dim Kalibrierungshinweis übersehbar | J2 | E=3 |
| L6 | Onboarding-Wizard visuell unpolished vs. Rest | J1 | V=3 |

---

## 5. Hero-Workflow

> **Definiton:** Der eine Workflow, der in drift exzellent sein muss — besser als "CLI + README" allein. Der Test: Startet ein Entwickler ohne Vorwissen und verlässt den Workflow mit einer *gemachten Handlung*, nicht nur einem Report?

### Empfehlung

```
drift setup (oder drift init --interactive)
    → drift status          # Ist das Projekt gesund?
    → drift analyze         # Was genau ist falsch?
    → drift fix-plan        # Was soll ich zuerst tun?
    → [manueller Fix]
    → drift status          # Hat es geholfen?
```

**Warum dieser Workflow?**

- Deckt Onboarding (J1), Tages-Loop (J2), Scan (J3) und Fix-Zyklus (J4) in einem Zug ab
- Der User endet mit einer verifizierten Verbesserung — messbarer Effekt, nicht nur Diagnose
- Genau dieser Loop unterscheidet ein Tool ("zeigt Probleme") von einer App-Erfahrung ("führt zur Lösung")

### Ist-Score des Hero-Workflows (Ø über J1+J2+J3+J4)

| Dimension | J1 | J2 | J3 | J4 | **Ø** | Lücke? |
|-----------|----|----|----|----|-------|--------|
| K Klarheit | 3 | 4 | 4 | 3 | **3.5** | Moderat |
| R Reibung | 4 | 5 | 3 | 3 | **3.75** | Moderat |
| Ko Konsistenz | 3 | 4 | 4 | 4 | **3.75** | Moderat |
| F Feedback | 3 | 4 | 4 | 3 | **3.5** | Moderat |
| E Fehler | 3 | 3 | 4 | 4 | **3.5** | Moderat |
| G Geschwindigkeit | 5 | 4 | 3 | 4 | **4.0** | Klein |
| V Visueller Fokus | 3 | 4 | 3 | 3 | **3.25** | Größte Lücke |

**Fazit:** Der Hero-Workflow liegt bei Ø ~3.6 — solide, aber nicht außergewöhnlich. Der visuelle Fokus (V=3.25) ist die größte Hemmung: Onboarding-Wizard und Fix-Workflow fühlen sich unfertig an im Vergleich zu `drift brief`.

---

## 6. Priorisierte nächste Aktionen

Geordnet nach Wirkung auf Hero-Workflow-Score:

| Prio | Aktion | Betroffene Lücke | Wirkung |
|------|--------|------------------|---------|
| 1 | **Onboarding-Pfad konsolidieren:** `drift init` als alleinigen Wizard-Befehl etablieren, `drift setup` als Alias belassen oder entfernen. Wizard visuell auf `drift brief`-Niveau heben (Panels, farbige Bestätigung). | L1, L6 | J1: Ko+1, V+1 |
| 2 | **Fix-Loop-Abschluss:** Nach `drift fix-plan --apply` (oder nach erneutem `drift status`) explizite Verbesserungsbestätigung zeigen: "Score verbessert von X auf Y". | L2 | J4: F+1, R+1 |
| 3 | **Baseline-Onboarding:** Nach `--update-baseline` explizit ausgeben: "Baseline gespeichert: `.drift/baseline.json` (2026-04-18, Score: X.XX)". Bei `drift trend` ohne Baseline: "Noch keine Baseline vorhanden — führe `drift analyze --update-baseline` aus." | L3 | J5: K+1, F+1 |
| 4 | **Profile-Fallback sichtbar machen:** Bei auto-fallback auf `vibe-coding` ein gelbes `[yellow]⚠ Profil 'X' nicht gefunden — Fallback: vibe-coding[/yellow]` zeigen. | L5 | J2: E+1 |
| 5 | **Scan-ETA:** Bei Phasen >5s eine ETA-Schätzung im Fortschrittsbalken ergänzen (z. B. `Analyzing… [■■■□□] 3/5 signals · ~8s remaining`). | L4 | J3, J5, J6: G+1 |

---

## 7. Messkriterien für "außergewöhnlich gut"

Ein Ziel-Score ≥4.5 pro Dimension im Hero-Workflow entspricht Apple-Niveau für ein CLI-Tool.

| Dimension | Aktuell (Hero-Ø) | Ziel | Messmethode |
|-----------|-----------------|------|-------------|
| K Klarheit | 3.5 | ≥4.5 | User-Test: Versteht Erstnutzer ohne Docs was als nächstes kommt? |
| R Reibung | 3.75 | ≥4.5 | Anzahl Aktionen bis zur ersten Verbesserung zählen (Ziel: ≤4) |
| Ko Konsistenz | 3.75 | ≥4.5 | Gleiche Begriffe in allen Command-Outputs? (Terminologie-Audit) |
| F Feedback | 3.5 | ≥4.5 | Gibt es nach jeder Aktion eine klare System-Reaktion? |
| E Fehler | 3.5 | ≥4.5 | Enthält jede Fehlermeldung "Was tun"? |
| G Geschwindigkeit | 4.0 | ≥4.5 | ETA sichtbar bei Läufen >5s? |
| V Visueller Fokus | 3.25 | ≥4.5 | Gibt es für jeden Screen genau 1 Hauptaussage? |

---

## Anhang: Methodik

**Heuristik-Quellen:**
- Apple HIG: Onboarding, Feedback, Status, Clarity
- Nielsen-Norman-Heuristiken: Sichtbarkeit des Systemstatus, Übereinstimmung mit der realen Welt, Fehlervermeidung, Hilfe bei Fehlern, Konsistenz und Standards
- UX Pilot Usability Heuristics (2024)

**Basis:**
- Statische Analyse der Ausgaben in `src/drift/commands/` (setup, status, analyze, fix_plan, brief)
- Kein Live-User-Test — Scores sind Heuristik-Schätzungen

**Nächster Validierungsschritt:**
- 3–5 Entwickler führen den Hero-Workflow ohne Anleitung aus
- Beobachte: Wo zögern sie? Wo verlassen sie den Workflow?
- Re-Scoring nach User-Test

---

*Erstellt: 2026-04-18 · Methode: Heuristik-Review · Nächste Revision: nach erstem User-Test*

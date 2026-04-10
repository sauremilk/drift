---
id: ADR-043
status: proposed
date: 2026-04-10
supersedes:
---

# ADR-043: Guided Mode — `drift status` und `drift setup`

## Kontext

Eine wachsende Nutzergruppe ("Vibe-Coder") generiert Code primär über KI-Assistenten ohne formale Programmierausbildung. Diese Nutzer erkennen Symptome architektonischer Erosion — der Assistent wird mit der Zeit unzuverlässiger — können aber die Ursache weder diagnostizieren noch beheben.

drift erkennt exakt diese Probleme. Das `vibe-coding`-Profil ist bereits kalibriert. Die Lücke besteht ausschließlich auf der Ausgabe-Ebene: Die richtigen Signale werden gefunden, aber nicht in einer Form kommuniziert, die ohne Vorwissen verwertbar ist.

Referenz: PRD `drift-guided-mode-prd-v2.md` (v1.1, 2026-04-10).

## Entscheidung

### Was wird getan

1. **Neues Kommando `drift status`** — Ampelstatus (🟢/🟡/🔴) mit alltagssprachlicher Headline und copy-paste-fertigem Prompt für KI-Assistenten. Kein Signal-Code, kein numerischer Score in der Standard-Ausgabe. Exit Code immer 0.

2. **Neues Kommando `drift setup`** — Interaktives Onboarding (≤ 2 Fragen, < 60 Sekunden). Erstellt `drift.yaml` mit Profil-Wahl und Spracheinstellung. Backup-Logik bei bestehender Datei.

3. **Guided Output Layer** — Template-basierte deutsche Alltagstexte für alle 18 scoring-aktiven Signale. Deterministisch, keine LLM-Abhängigkeit, keine externe Verbindung.

4. **Config-Erweiterungen** — Optionale Felder `language` (DriftConfig), `guided_thresholds` und `output_language` (Profile). Rückwärtskompatibel mit Defaults.

5. **OD-01** — `drift` ohne Argument delegiert bei `profile: vibe-coding` auf `drift status`.

### Was explizit nicht getan wird

- Keine Änderung an der Analyse-Engine (pipeline, signals, scoring, models)
- Keine Änderung an bestehenden Kommandos (analyze, check, fix-plan, explain)
- Keine LLM-basierte Textgenerierung
- Keine englischsprachige Ausgabe (geplant für v3.1.0)
- Keine MCP-Server-Integration für `drift status` (geplant für v3.1.0)
- Keine nutzer-konfigurierbaren Ampel-Schwellwerte

## Begründung

### Template statt LLM

Template-basierte Ausgabetexte sind deterministisch, erfordern keine externe Verbindung und produzieren keine Halluzinationen. Die Qualitätsobergrenze gut entworfener Templates ist für diesen Use Case ausreichend und überprüfbar.

### Exit Code 0 für alle Ampelstatus

`drift status` ist ein Informationskommando. Maschinenlesbare Gates verwenden `drift check --fail-on`. Ein Exit Code ≠ 0 bei RED würde Persona A (Vibe-Coder) irreführen.

### Score wird nicht angezeigt

Die Ampel ist die Abstraktion des Scores. Beide gleichzeitig anzuzeigen würde die Semantik der Ampel entwerten. Wer den Score benötigt, nutzt `drift analyze`.

### `can_continue=False` ab YELLOW

Das semantische Signal richtet sich an integrierende Tools. Ab YELLOW besteht ein strukturelles Problem, das sich ohne Eingriff verschlimmert.

### Schwellwerte nicht nutzer-konfigurierbar

Guided Mode richtet sich explizit an Nutzer, die keine Konfiguration vornehmen. Für fortgeschrittene Gate-Konfiguration existiert `drift check --fail-on`.

### Alternativen verworfen

- **LLM-generierte Texte:** Nicht-deterministisch, erfordert API-Key, Halluzinationsrisiko.
- **Nur `drift analyze --simple`:** Verändert bestehende Kommando-Semantik (F-21 verletzt).
- **Konfigurierbare Schwellwerte:** Widerspruch zum Designziel "konfigurationsarm für Anfänger".

## Konsequenzen

- **Neue Dateien (4):** `commands/status.py`, `commands/setup.py`, `output/guided_output.py`, `output/prompt_generator.py`
- **Geänderte Dateien (5):** `cli.py`, `profiles.py`, `config.py`, `finding_rendering.py`, `output/__init__.py`
- **Ampel-Schwellwerte:** Für `vibe-coding`: GREEN < 0.35, YELLOW 0.35–0.64, RED ≥ 0.65 — empirisch zu validieren post-Release
- **18 deutsche Prompt-Templates** zu pflegen — manueller Review-Aufwand bei Signal-Änderungen
- **Keine Auswirkung auf bestehende API-Contracts** — reine Addition

## Validierung

```bash
# Unit-Tests Guided Output Layer
pytest tests/test_guided_output.py tests/test_prompt_generator.py -v

# CLI-Integration
pytest tests/test_status_command.py -v

# Vollständigkeitstest: 18/18 Signale mit Guided-Texten
pytest tests/test_guided_output.py -k "test_signal_completeness" -v

# Rückwärtskompatibilität
make test-fast

# Selbstanalyse unverändert
drift analyze --repo . --format json --exit-zero
```

**Lernzyklus-Ergebnis (§10):** `unklar` — empirische Validierung der Schwellwerte auf ≥ 10 Repositories nach Release erforderlich. Prompt-Qualität erfordert Nutzerfeedback.

---
id: ADR-043
status: proposed
date: 2026-04-10
supersedes:
---

# ADR-043: Guided First-Run Experience - `drift status`, `drift setup` und `drift analyze`

## Kontext

Eine wachsende Nutzergruppe ("Vibe-Coder") generiert Code primaer ueber KI-Assistenten ohne formale Programmierausbildung. Diese Nutzer erkennen Symptome architektonischer Erosion - der Assistent wird mit der Zeit unzuverlaessiger - koennen aber die Ursache weder diagnostizieren noch beheben.

drift erkennt exakt diese Probleme. Das `vibe-coding`-Profil ist bereits kalibriert. Die Luecke liegt auf der Ausgabe-Ebene: Die richtigen Signale werden gefunden, aber weder `drift analyze` noch Guided Mode priorisieren den ersten sinnvollen Schritt konsequent genug fuer den Erstkontakt.

Referenz: PRD `drift-guided-mode-prd-v2.md` (v1.1, 2026-04-10).

## Entscheidung

### Was wird getan

1. **`drift status` als Guided Entry Point** - Ampelstatus mit alltagssprachlicher Headline, priorisierten Top-Findings und copy-paste-fertigem Prompt fuer KI-Assistenten. Kein Signal-Code, kein numerischer Score in der Standard-Ausgabe. Exit Code immer 0.

2. **`drift setup` fuer leichtgewichtiges Onboarding** - Interaktives Onboarding (<= 2 Fragen, < 60 Sekunden). Erstellt `drift.yaml` mit Profil-Wahl und Spracheinstellung. Backup-Logik bei bestehender Datei.

3. **Shared First-Run Summary Contract** - Eine gemeinsame Priorisierungs- und Summary-Schicht liefert fuer `drift analyze` und `drift status` dieselben Startpunkte: priorisierte Top-Findings, kurzer Bedeutungsrahmen und den naechsten konkreten Schritt.

4. **Guided Output Layer** - Template-basierte deutsche Alltagstexte fuer alle scoring-aktiven Signale. Deterministisch, keine LLM-Abhaengigkeit, keine externe Verbindung.

5. **`drift analyze` bekommt eine First-Run-Zusammenfassung** - Rich- und JSON-Ausgabe erhalten zusaetzlich einen kompakten Block, der vor Detailtabellen beantwortet: Was ist jetzt wichtig? Warum sollte ich anfangen? Was ist der erste sinnvolle Schritt?

6. **Config-Erweiterungen** - Optionale Felder `language` (DriftConfig), `guided_thresholds` und `output_language` (Profile). Rueckwaertskompatibel mit Defaults.

7. **OD-01** - `drift` ohne Argument delegiert bei `profile: vibe-coding` auf `drift status`.

### Was explizit nicht getan wird

- Keine Aenderung an der Analyse-Engine (pipeline, signals, scoring, models)
- Keine Aenderung an `check`, `fix-plan`, `brief`, `explain` oder MCP-Contracts
- Keine LLM-basierte Textgenerierung
- Keine englischsprachige Guided-Ausgabe (geplant fuer v3.1.0)
- Keine MCP-Server-Integration fuer `drift status` (geplant fuer v3.1.0)
- Keine nutzer-konfigurierbaren Ampel-Schwellwerte

## Begruendung

### Shared Contract statt Kommando-spezifischer Duplikate

Priorisierung, erster naechster Schritt und Auswahl der wichtigsten Findings duerfen nicht in `status`, `analyze` und JSON-Ausgabe auseinanderlaufen. Ein gemeinsamer Contract reduziert Inkonsistenzen und verhindert, dass Nutzer je nach Kommando andere Einstiegspunkte sehen.

### Template statt LLM

Template-basierte Ausgabetexte sind deterministisch, erfordern keine externe Verbindung und produzieren keine Halluzinationen. Die Qualitaetsobergrenze gut entworfener Templates ist fuer diesen Use Case ausreichend und ueberpruefbar.

### Exit Code 0 fuer alle Ampelstatus

`drift status` ist ein Informationskommando. Maschinenlesbare Gates verwenden `drift check --fail-on`. Ein Exit Code != 0 bei RED wuerde Persona A (Vibe-Coder) irrefuehren.

### Score wird in Guided Mode nicht angezeigt

Die Ampel ist die Abstraktion des Scores. Beide gleichzeitig anzuzeigen wuerde die Semantik der Ampel entwerten. Wer den Score benoetigt, nutzt `drift analyze`.

### `can_continue=False` ab YELLOW

Das semantische Signal richtet sich an integrierende Tools. Ab YELLOW besteht ein strukturelles Problem, das sich ohne Eingriff verschlimmert.

### Schwellwerte nicht nutzer-konfigurierbar

Guided Mode richtet sich explizit an Nutzer, die keine Konfiguration vornehmen. Fuer fortgeschrittene Gate-Konfiguration existiert `drift check --fail-on`.

### Alternativen verworfen

- **LLM-generierte Texte:** Nicht-deterministisch, erfordert API-Key, Halluzinationsrisiko.
- **Nur `drift analyze --simple`:** Veraendert bestehende Kommando-Semantik und trennt Guided-Mode-Priorisierung nicht sauber von der Detailanalyse.
- **Konfigurierbare Schwellwerte:** Widerspruch zum Designziel "konfigurationsarm fuer Anfaenger".

## Konsequenzen

- Guided Mode bleibt additionell, bekommt aber einen gemeinsamen Summary-Kern fuer `status` und `analyze`.
- Zusaetzlich zu bestehenden Guided-Mode-Dateien werden `commands/analyze.py`, `output/rich_output.py` und `output/json_output.py` erweitert.
- Ampel-Schwellwerte fuer `vibe-coding`: GREEN < 0.35, YELLOW 0.35-0.64, RED >= 0.65 - empirisch zu validieren post-Release.
- Deterministische Priorisierung wird zum wiederverwendbaren Contract zwischen CLI-Ausgaben.
- Der JSON-Contract erweitert sich additiv um einen First-Run-Block; bestehende Felder bleiben erhalten.

## Validierung

```bash
# Unit-Tests Guided Output Layer / First-Run-Contract
pytest tests/test_guided_mode.py tests/test_json_output.py -v

# CLI-Integration
pytest tests/test_guided_mode.py -k "status or first_run" -v

# JSON-/Rich-Ausgabe bleibt rueckwaertskompatibel
pytest tests/test_output_golden.py -v

# Rueckwaertskompatibilitaet
make test-fast

# Selbstanalyse unveraendert
drift analyze --repo . --format json --exit-zero
```

**Lernzyklus-Ergebnis (§10):** `unklar` - empirische Validierung der Schwellwerte auf >= 10 Repositories nach Release erforderlich. Prompt-Qualitaet erfordert Nutzerfeedback.

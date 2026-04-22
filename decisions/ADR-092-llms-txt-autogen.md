---
id: ADR-092
status: proposed
date: 2026-05-04
supersedes:
---

# ADR-092: `llms.txt` deterministisch aus `signal_registry` generieren (Paket 1C)

## Kontext

`llms.txt` ist drifts öffentliche Discovery-Oberfläche für LLM- und
Agent-Konsumenten. Sie listet das aktuelle Release, die 25 Kern-Signale
mit Abkürzung, Namen und Gewicht und trennt Scoring-aktive von
Report-only Signalen. Die Datei wurde bisher von Hand gepflegt und
stichprobenartig in `scripts/check_model_consistency.py` validiert.

Dabei sind mehrere Drift-Quellen aufgetreten:

* **Veraltete Release-Status-Zeile.** `scripts/sync_version.py` kannte
  zwar das Regex-Format, korrigierte aber nur reaktiv im Pre-Push-Hook.
  Auf `main` stand zeitweise `Release status: v2.30.0`, obwohl
  `pyproject.toml` bereits auf `v2.32.0` lag.
* **Unvollständige Abdeckung in `check_model_consistency.py`.** Die
  handgepflegte `code_to_key`-Tabelle in `_check_llms_txt` deckte nur
  15 der 25 Signale ab. Neue Signale (`MAZ`, `PHR`, `HSC`, `ISD`,
  `FOE`, `CXS`, `CIR`, `DCA`, `TSA`, `TSB`) blieben ungeprüft.
* **Fehlendes Signal.** `TSB` (Type Safety Bypass) war in
  `signal_registry` registriert, aber nie in `llms.txt` aufgenommen –
  die Discovery-Datei hat das Signal somit stillschweigend
  unterschlagen.
* **Keine deterministische Sortierung.** Die Reihenfolge war
  editorial. Änderungen an Gewichten oder Signalzusätzen erforderten
  Meinungsentscheidungen statt einfacher Regeneration.

Dieses Muster entspricht dem Anti-Pattern, das drift selbst als
`doc_impl_drift` (DIA) und `explainability_deficit` (EDS) meldet: zwei
Quellen der Wahrheit, die manuell synchron gehalten werden müssen.

## Entscheidung

`llms.txt` wird als vollständig deterministisches Build-Artefakt
behandelt und aus autoritativen Quellen regeneriert.

### Generator

Neu: `scripts/generate_llms_txt.py`.

* **Eingaben.** `pyproject.toml` (Version),
  `src/drift/signal_registry.py` (Signal-Metadaten über `get_all_meta()`),
  kleiner `_DOC_OVERRIDES`-Dict für SEO-getunte Anzeigenamen und
  CWE-Footnotes (MAZ→CWE-862, HSC→CWE-798, ISD→CWE-1188, PHR→AI
  hallucination indicator).
* **Modi.** `--write` (Default, schreibt `llms.txt` neu) und `--check`
  (exit 1 + unified diff, wenn Datei auf der Platte von der
  Soll-Ausgabe abweicht).
* **Bestimmtheit.** Identische Eingaben erzeugen byte-identischen
  Output. Sortierung: Scoring-aktive Signale nach Gewicht absteigend,
  Ties nach Abkürzung aufsteigend; Report-only nach Abkürzung.
* **Stabile Prosa.** Alle nicht-signalabhängigen Abschnitte
  (Header-Tagline, Two-Modes-Block, Fact-Grounding-Contract,
  Use-Cases, Benchmarks, Docs-Links, Keywords) stehen als String-
  Konstanten im Generator. Änderungen dort sind Policy-relevant und
  gehen über einen normalen Commit.

### Pre-Push-Hook

`.githooks/pre-push` Schritt `[0/6]` wird erweitert: Zusätzlich zu
`scripts/sync_version.py --fix` wird `scripts/generate_llms_txt.py`
ausgeführt. Bei Drift werden beide Repair-Kommandos in genau einem
`chore: sync version refs`-Commit gebündelt. Vorhandener Bypass
`DRIFT_SKIP_VERSION_SYNC=1` deckt auch den neuen Schritt ab.

### Release-Workflow

`.github/workflows/release.yml` ruft nach `sync_version.py` zusätzlich
`generate_llms_txt.py --write` auf, stagt `llms.txt` und amend+re-tagt
nur, wenn tatsächlich Dateien geändert wurden. Damit kommt das neue
Release immer mit einer synchronen Discovery-Datei.

### Model-Consistency-Check

`scripts/check_model_consistency.py` behält die öffentlichen
Funktionen `_check_llms_txt` und `_check_version_refs`, delegiert
aber intern an `scripts/generate_llms_txt.py --check`. Die 15-Signal-
`code_to_key`-Tabelle wird entfernt; die neue Prüfung deckt alle
Signale über das gleiche Regelwerk wie der Generator ab.

### Tests

Neu: `tests/test_llms_txt_generator.py` mit sieben Tests:

1. `--check` exit 0 auf sauberem Baum.
2. Wiederholte Generation ist idempotent.
3. `--check` erkennt künstliche Drift.
4. Versionszeile stimmt mit `pyproject.toml` überein.
5. Alle Kern-Signal-Abkürzungen aus `signal_registry` sind
   gerendert.
6. Header-Counts "Scoring-active (N)" und "Report-only (M)"
   stimmen mit dem Registry überein.
7. Jedes gerenderte Gewicht entspricht dem Registry-Default.

## Konsequenzen

**Positiv.**

* Eine Quelle der Wahrheit für Signal-Gewichte: `signal_registry`.
* Neue Signale erscheinen automatisch in `llms.txt`, sobald sie
  registriert sind – der Pre-Push-Hook regeneriert.
* CI-Gate und Pre-Push-Gate nutzen dasselbe Generator-Programm.
* `llms.txt`-Drift wird vom Hook stillschweigend repariert, nicht
  manuell verlangt.

**Negativ / Trade-offs.**

* Prosa-Änderungen am Generator erfordern Code-Review statt Markdown-
  Edit. Das ist bewusst (Policy-Gate greift).
* Die Sortierung ändert sich einmalig zur deterministischen Reihenfolge
  (AVS vor PFS bei Gewichtsgleichstand). Discovery-Konsumenten, die
  sich auf exakte Zeilenreihenfolge verlassen, müssen sich einmalig
  umstellen.
* Benötigt Python 3.11+ (tomllib) – bereits Projektminimum.

**Nicht im Scope.**

* `README.md`, `SECURITY.md` und `docs/`-Inhalte bleiben manuell.
  ADR-092 limitiert sich auf die Discovery-Oberfläche `llms.txt`.
* `drift.output.schema.json` hat einen eigenen Generator (Paket 1B /
  `scripts/generate_output_schema.py`).

## Risiken und Audit

Erfasst in:

* `audit_results/fmea_matrix.md` – neue Zeile `FMEA-LLMS-01:
  Discovery-Drift durch unentdeckten Signal-Registry-Zuwachs`.
* `audit_results/risk_register.md` – Eintrag
  `RISK-LLMS-01: öffentliche Discovery-Datei widerspricht tatsächlichem
  Signalumfang` mit Severity "Medium", Mitigation "Pre-Push-Hook +
  CI-Check regenerieren deterministisch".

Kein STRIDE- oder Fault-Tree-Update nötig: Der Generator ändert keine
Trust Boundary, verarbeitet keine externen Eingaben und berührt weder
Scoring noch Signal-Detektoren.

## Validierung

* `python scripts/generate_llms_txt.py --check` → exit 0.
* `python -m pytest tests/test_llms_txt_generator.py` → 7/7 pass.
* Simulierte Signal-Erweiterung → Pre-Push-Hook auto-regeneriert und
  committet.
* `scripts/check_model_consistency.py` Checks 5+6 weiterhin grün
  (Delegation).

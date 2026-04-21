---
id: ADR-083
status: proposed
date: 2026-04-21
supersedes:
---

# ADR-083: Agent Pre-Edit Pattern-Scan via drift_steer

## Kontext

Im Field-Test am 2026-04-21
(`work_artifacts/reduce_findings_2026-04-21/`) hat ein Agent im Rahmen
eines `extract_function`-Fix-Loops neue PFS-Findings eingeführt:

- `error_handling: 5 variants in scripts/` (severity HIGH)
- `return_pattern: 2 variants` (severity MEDIUM)

Die neuen Hilfsfunktionen verwendeten andere Error-Handling- und
Return-Patterns als der Rest des Verzeichnisses. Das ist keine
Drift-Bug-Klasse (siehe ADR-082 für den Fingerprint-Anteil), sondern
eine vermeidbare Agent-Inkonsistenz: der Agent kennt zum Edit-Zeitpunkt
das dominante Pattern im Zielverzeichnis nicht.

Der vorhandene `drift_steer`-Endpunkt
(`src/drift/api/steer.py`) liefert bereits Architecture-Kontext für
einen Target. Er wird im Fix-Loop-Prompt bisher aber nur erwähnt und
nicht als Pflichtschritt vor dem Edit verlangt.

## Entscheidung

Der Fix-Loop-Prompt
(`.github/prompts/drift-fix-loop.prompt.md`) erhält einen
verpflichtenden Pre-Edit-Schritt:

> Bevor ein Edit, das neue Funktionen oder Klassen einführt
> (typisch: `extract_function`, `extract_class`, Helper-Refactoring),
> ausgeführt wird, MUSS der Agent `drift_steer(target=<zieldatei>)`
> aufrufen und das Ergebnis als harte Constraint für den Edit
> interpretieren.

Konkret:

- Wenn `drift_steer` `patterns_used_in_scope` liefert, sind die dort
  genannten dominanten Patterns (error_handling, return_pattern,
  logging, etc.) verbindlich für neue Helfer.
- Wenn `drift_steer` keine expliziten Patterns liefert, gilt als
  Fallback: neue Helfer folgen dem Stil des umgebenden Codes innerhalb
  derselben Datei.
- Die Pflicht gilt nur für Edits, die neue Symbole einführen, nicht
  für reine In-Place-Änderungen an bestehendem Code.

**Nicht Teil dieser Entscheidung:**

- Keine Code-Erweiterung von `drift_steer` in diesem ADR. Wenn
  `patterns_used_in_scope` heute noch nicht geliefert wird, gilt der
  Fallback. Eine spätere ADR kann `drift_steer` um explizite
  Pattern-Extraktion erweitern.
- Kein automatisches Blockieren des Edits ohne Steer-Aufruf. Die
  Regel ist prompt-seitig durchgesetzt, nicht tool-seitig.

## Begründung

**Warum Prompt-seitig und nicht Tool-seitig?** Ein Tool-seitiges
Enforcement (z. B. `drift_patch_begin` lehnt Edits ohne vorherigen
Steer-Aufruf ab) wäre spröde und würde non-agent-Workflows stören.
Prompt-seitige Pflicht ist hinreichend, weil der Fix-Loop-Prompt die
primäre Interaktionsform ist.

**Warum `drift_steer` und nicht `drift_brief`?** `drift_brief` ist
task-orientiert (*was soll getan werden?*), `drift_steer` ist
location-orientiert (*was gilt an diesem Ort?*). Für einen Edit, der
sich auf eine Zieldatei bezieht, liefert steer die bessere
Information-Dichte.

**Alternativen verworfen:**

- *Automatische Pattern-Prüfung nach Edit* (`drift_nudge`): funktioniert,
  fängt den Fehler aber erst nachträglich. Revert + Retry ist teurer
  als einmal steer vor dem Edit.
- *Separate ADR für drift_steer-Erweiterung*: ja, aber nicht Teil
  dieses ADRs. Diese Entscheidung ist sofort umsetzbar ohne
  Code-Änderung.

## Konsequenzen

**Positiv:**

- PFS-FP-Rate bei Agent-Refactorings sinkt.
- Schafft eine klare Vertragsfläche für künftige
  `drift_steer`-Erweiterungen (patterns_used_in_scope).
- Agent wird zu pattern-bewussten Refactorings erzogen — Transferwert
  auch außerhalb des Fix-Loops.

**Trade-offs:**

- Ein zusätzlicher MCP-Roundtrip pro Extract-Edit (~100–300 ms).
  Akzeptabel gegenüber dem Retry-Kostenprofil bei Revert.
- Prompt wird länger. Gemildert durch klare Regel-Trennung und
  Verweis in Skill-Datei.

## Validierung

Die Entscheidung gilt als validiert, wenn:

1. Die Prompt-Änderung in
   `.github/prompts/drift-fix-loop.prompt.md` einen eindeutigen
   Pre-Edit-Schritt mit `drift_steer`-Aufruf enthält.
2. Der Skill
   `.github/skills/drift-effective-usage/SKILL.md` einen Abschnitt
   "Helper-Extraktion ohne Pattern-Drift" enthält, der auf diese Regel
   verweist.
3. Im nächsten Field-Test (Evidenz aus ADR-082) die Anzahl neuer
   PFS-Findings pro Extract-Fix **deutlich geringer** ist als im
   Baseline-Field-Test vom 2026-04-21.

Lernzyklus-Ergebnis-Kategorie (POLICY.md §10): erwartet `bestätigt`
nach Field-Test-Re-Run.

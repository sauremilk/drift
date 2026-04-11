---
id: ADR-032
status: proposed
date: 2026-04-09
supersedes:
---

# ADR-032: Hard Completion Gate fuer False-Fix und Relocation in drift_diff

## Kontext

Issue #205 beschreibt ein Vertrauensproblem im Abschlusskriterium von `drift_diff`:
Eine Aenderung kann als akzeptiert erscheinen, obwohl die Ursache nur kosmetisch bearbeitet oder in eine andere Stelle verlagert wurde.

Die bisherigen Blocking-Reasons (Severity/Score/Noise) erfassen diese Klasse von Scheinerfolgen nicht explizit.
Damit sinken Nachvollziehbarkeit und Handlungsfaehigkeit bei Agent-gestuetzten Fix-Loops.

## Entscheidung

`drift_diff` wird um einen harten Completion-Gate erweitert:

1. Explizite Erkennung und Ausweisung von
   - `false_fix_suspected`
   - `relocation_suspected`
   - `evidence_links`
2. `accept_change` bleibt nur dann `true`, wenn keine klassischen Blocking-Reasons vorliegen **und** keine kosmetische/relokative Scheinkorrektur erkannt wurde.
3. Die Erkennung basiert auf deterministischer Cause-Class-Ableitung (Signal-Familie + stabilisierte Ursache) und standortbezogener Evidenz.

Nicht Teil dieser ADR:

- Aenderung von Signal-Gewichten
- Redesign der Scoring-Formel
- UI-Textaenderungen ohne Gate-Logik

## Begruendung

Die Entscheidung priorisiert Policy-Stufe 1 (Vertrauen/Glaubwuerdigkeit):
Ein harter Gate fuer Scheinkorrekturen verhindert "apparent progress" und erhoeht die Aussagekraft von `accept_change`.

Alternativen (nur Hinweistext ohne Gate, oder manuelle Agent-Interpretation) wurden verworfen,
weil sie nicht deterministisch sind und weiterhin zu inkonsistenten Merge-Entscheidungen fuehren.

## Konsequenzen

- Positiv:
  - Klarere Kausalzuordnung bei Relocation-Faellen
  - Besser reproduzierbare Gate-Entscheidungen
  - Explizite Evidenz fuer Review, CI und Agent-Loop
- Trade-off:
  - Konservativeres Verhalten von `accept_change` in Randfaellen
  - Zusatzlogik im Diff-Pfad, die testseitig stabil gehalten werden muss

## Validierung

```bash
.\.venv\Scripts\python.exe -m pytest tests/test_telemetry.py -q --maxfail=1
.\.venv\Scripts\python.exe -m pytest tests/test_agent_native_cli.py -q --maxfail=1
.\.venv\Scripts\python.exe -m pytest tests/ --tb=short --ignore=tests/test_smoke.py --ignore=tests/test_smoke_real_repos.py -q --maxfail=1
```

Erwartetes Lernzyklus-Ergebnis: `bestaetigt`, wenn alle Punkte gelten:

- kosmetische Fixes erzeugen blockierende Begruendung
- Relocation-Faelle erzeugen nachvollziehbare Cause-Chain-Evidenz
- AVS/PFS/MDS-Familien sind jeweils durch mindestens einen API-E2E-Testfall abgedeckt
- Response-Schema bleibt rueckwaertskompatibel erweitert (additive Felder)
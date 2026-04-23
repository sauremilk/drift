---
id: ADR-NNN
status: proposed
date: YYYY-MM-DD
type: signal-design
signal_id: XXX
supersedes:
---

# ADR-NNN: Signal Design — [Signal-Name] ([Kürzel])

## Problemklasse

[Welches Kohärenzproblem wird erkannt? Referenz auf Policy §4.2.]

## Heuristik

[Wie wird das Signal berechnet? Pseudocode oder klare Beschreibung.]

## Scope

[`file_local` | `cross_file` | `git_dependent` — mit Begründung.]

## Erwartete FP-Klassen

[Welche False Positives sind vorhersehbar? Akzeptanzschwelle.]

## Erwartete FN-Klassen

[Welche Fälle wird das Signal systematisch verpassen?]

## Fixture-Plan

[Welche Minimal-Fixtures müssen existieren, bevor die Implementierung beginnt?]

## FMEA-Vorab-Eintrag

| Failure Mode | Severity | Occurrence | Detection | RPN |
|---|---|---|---|---|
| [FM-Beschreibung] | [1–10] | [1–10] | [1–10] | [S×O×D] |

## Validierungskriterium

[Messbare Aussage, ab wann das Signal als funktionierend gilt. Referenz auf Policy §10 Lernzyklus-Ergebnis.]

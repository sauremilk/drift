# 07 — `drift patch --auto` Apply-and-Verify Loop (Epoche B)

> **Zweck:** Autonome Patch-Anwendung mit Verify-Loop für die
> hochpräzisen Signale, damit Drift nicht nur diagnostiziert, sondern
> für klar definierte Muster auch remediiert.
>
> **Status:** proposed — **blockiert durch Phase-B-Validierungsergebnis
> gemäß [ADR-084](../docs/decisions/ADR-084-positionierung-vibe-coding-tool.md)**
> **Erstellt:** 2026-04-21
> **Status: active, siehe ADR-084 Option C. Sub-ADR erforderlich vor Code-Änderungen.**
> **Erfordert vor Beginn:** eigene ADR pro Signal-Familie

---

## Idee (informativ, nicht spezifiziert)

Die Patch-Engine existiert seit v2.14 (siehe
`benchmark_results/v2.14.0_patch_engine_feature_evidence.json`).
Heute fehlt ein zuverlässiger Apply-Verify-Loop für die Signale mit
nachgewiesen hoher Precision (Kandidaten: MDS, PFS, EDS).

Erwarteter Ablauf:

1. Drift erzeugt Patch-Vorschlag pro Finding (Dry-Run-Default)
2. Loop wendet Patch in Sandbox an
3. `drift_nudge` verifiziert Richtungssignal (`improving` / `degrading`)
4. Mensch entscheidet über Merge — nicht über jeden Einzelschritt

## Gating

**Status: active, siehe ADR-084 Option C. Sub-ADR erforderlich
vor Code-Änderungen.** Zusätzlich pro Signal eine eigene ADR notwendig
(Auto-Patch ist eine Trust-Boundary nach POLICY §18).

## Nicht Teil dieser Aufgabe

- Keine Implementierung.
- Keine Auswahl der konkreten Signal-Familie ohne Precision-Recall-
  Nachweis aus `tests/test_precision_recall.py` und Mutation-Benchmark.
- Kein Auto-Merge — Mensch bleibt im Loop.

# 05 — drift_nudge Cold-Start Latenz

> **Zweck:** Cold-Start-Latenz von `drift_nudge` auf neuen Repos messbar
> reduzieren, damit `drift_nudge` als Agenten-Editing-Loop-Feedback ohne
> spürbare Wartezeit nutzbar bleibt.
>
> **Status:** proposed (sekundär gegenüber Item 04)
> **Erstellt:** 2026-04-21
> **Status: active, siehe ADR-084 Option C. Sub-ADR erforderlich vor Code-Änderungen.**
> **Verwandte Artefakte:** [ADR-084](../docs/decisions/ADR-084-positionierung-vibe-coding-tool.md), [`benchmark_results/mcp_performance_smoke.json`](../benchmark_results/mcp_performance_smoke.json), [`.github/copilot-instructions.md`](../.github/copilot-instructions.md) (Post-Edit-Drift-Nudge-Pflicht)

---

## Problem

Aktuelle Messung in [`benchmark_results/mcp_performance_smoke.json`](../benchmark_results/mcp_performance_smoke.json):

- `drift_nudge` mean: **4.687 s** (1 Call, in-process auf Self-Corpus)
- Folgende `drift_nudge`-Calls (warm baseline): typisch ~0.2 s
- Vergleich: `drift_scan` 1.203 s, `drift_brief` 0.11 s,
  `drift_session_start_autopilot` 0.453 s

Der Cold-Start ist im Agent-Workflow ein einmaliger Sprung, aber er
trifft jeden neuen Repo, jede frische Session und jedes Worktree-
Switch. In agentengetriebenen Workflows (Post-Edit-Drift-Nudge ist laut
`.github/copilot-instructions.md` Pflicht nach jeder Dateiänderung)
verstärkt sich der Effekt.

## Gating

**Status: active, siehe ADR-084 Option C. Sub-ADR erforderlich
vor Code-Änderungen.**

## Zielwert

Cold-Start `drift_nudge` auf einem repräsentativen Repo mit ~1000
Python-Files **< 1 s** (heute ~4.7 s auf Self-Corpus).

Messmethode: erweiterter Run von `scripts/_mcp_performance_smoke.py` (sofern
existent, sonst zu prüfen) mit explizit kaltem Cache. Ergebnis als
neuer Eintrag in `benchmark_results/mcp_performance_smoke.json` oder
einem dedizierten `cold_start_*.json`-Artefakt.

## Operative Schritte (entwurfsweise, nicht jetzt umsetzen)

- [ ] Profil-Run auf kaltem Cache erstellen (`pytest`-Marker oder
      Skript), um Bottleneck zu lokalisieren
- [ ] ADR drafen (eigene Nummer, blockierend) sobald Item 04 die
      Priorisierung freigibt
- [ ] Lazy-Initialization-Strategien evaluieren (Baseline-Carryforward
      ist bereits vorhanden — siehe `auto_fast_path` in
      `.github/copilot-instructions.md`)
- [ ] Erfolgsmessung: Vorher/Nachher-Vergleich in `benchmark_results/`
- [ ] Audit-Update prüfen (FMEA, Risk-Register) falls Caching-Verhalten
      sich materiell ändert (POLICY §18)

## Nicht Teil dieser Aufgabe

- Keine Architekturänderung an `drift_nudge` ohne ADR.
- Kein Refactoring der Baseline-Cache-Logik außerhalb des messbaren
  Cold-Start-Pfads.
- Keine Erweiterung der `drift_nudge`-Output-Felder.

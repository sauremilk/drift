# 06 — Trend-Gate Enforcement (Epoche B)

> **Zweck:** Konfigurierbare Gate-Eskalation auf Basis von Score-Trend
> über mehrere Commits, damit Drift autonome Agent-Workflows absichern
> kann statt nur statisch Schwellenwerte zu prüfen.
>
> **Status:** proposed — **blockiert durch Phase-B-Validierungsergebnis
> gemäß [ADR-084](../docs/decisions/ADR-084-positionierung-vibe-coding-tool.md)**
> **Erstellt:** 2026-04-21
> **Status: active, siehe ADR-084 Option C. Sub-ADR erforderlich vor Code-Änderungen.**
> **Erfordert vor Beginn:** eigene ADR für die Trend-Gate-Heuristik

---

## Idee (informativ, nicht spezifiziert)

Heute prüft Drift in CI typisch via `drift check` oder `--exit-zero`
gegen statische Schwellenwerte. Die strategische Analyse vom
21.04.2026 schlägt vor, Score-Verschlechterung **über N Commits ohne
Remediation-Aktivität** als zusätzliches Gate-Kriterium zu etablieren
(z. B. "Score +0.05 über 3 Commits ohne Fix-Aktivität → Block").

Vorhandene Bausteine:

- `drift diff` liefert Score-Vergleich gegen Baseline
- Telemetrie kann Edit-Aktivität sichtbar machen (POLICY §19)
- `drift check` und `--gate`-Output-Format sind die natürlichen
  Integrationspunkte

## Gating

**Status: active, siehe ADR-084 Option C. Sub-ADR erforderlich
vor Code-Änderungen.**

## Nicht Teil dieser Aufgabe

- Keine Implementierung. Dieses Item dokumentiert nur, dass der
  Gedanke in der Roadmap-Diskussion steht.
- Keine Festlegung der Heuristik (Schwelle, Fenstergröße, Reset-
  Bedingung) — gehört in eine eigene ADR sobald freigegeben.

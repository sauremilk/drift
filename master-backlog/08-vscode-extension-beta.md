# 08 — VS Code Extension (Beta) (Epoche B)

> **Zweck:** Inline-Finding-Overlay und Status-Bar-Score in VS Code,
> sodass Drift ohne Terminal-Wechsel im Editor sichtbar ist.
>
> **Status:** proposed — **blockiert durch Phase-B-Validierungsergebnis
> gemäß [ADR-084](../docs/decisions/ADR-084-positionierung-vibe-coding-tool.md)**
> **Erstellt:** 2026-04-21
> **Status: active, siehe ADR-084 Option C. Sub-ADR erforderlich vor Code-Änderungen.**
> **Erfordert vor Beginn:** eigene ADR für Extension-Architektur

---

## Idee (informativ, nicht spezifiziert)

Drift hat einen produktionsreifen MCP-Server. Eine VS-Code-Extension
braucht kein eigenes Backend — sie kann gegen den lokalen MCP-Server
laufen. Erwarteter Funktionsumfang einer Beta:

- Inline-Squigglies für Findings aus `drift_scan`
- Status-Bar-Score (heutiger `drift analyze`-Score)
- Code-Action für `drift_nudge` nach Edit
- Keine eigene Analyse-Logik — alles via MCP

## Gating

**Status: active, siehe ADR-084 Option C. Sub-ADR erforderlich
vor Code-Änderungen.** Zusätzlich:

- Eigene ADR für Extension-Repo-Strategie (Mono-Repo vs. separates Repo)
- Klärung MCP-Versions-Kompatibilitäts-Matrix
- Distribution-Strategie (VS-Code-Marketplace-Listing)

## Nicht Teil dieser Aufgabe

- Keine Implementierung.
- Keine Versprechen zu Sprach-Support außerhalb dessen, was
  `drift_scan` heute liefert.
- Keine eigene Telemetrie in der Extension — vorhandene Drift-
  Telemetrie via MCP nutzen, POLICY §19 respektieren.

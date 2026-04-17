---
name: guard-src-drift-serve
description: "Drift-generierter Guard fuer `src/drift/serve`. Aktiv bei Signalen: PFS. Konfidenz: 0.62. Verwende diesen Skill wenn du Aenderungen an `src/drift/serve` planst oder wiederholte Drift-Findings (PFS) fuer dieses Modul bearbeitest."
argument-hint: "Beschreibe welches MCP-Tool (neues Tool, geaenderter Handler, Routing-Aenderung) betroffen ist."
---

# Guard: `src/drift/serve`

`src/drift/serve` enthaelt den MCP-Server: Tool-Registrierung, Request-Routing und die MCP-Protokoll-Implementierung. PFS entsteht wenn neue Tool-Handler nicht demselben Registrierungs- und Routing-Muster folgen wie bestehende.

**Konfidenz: 0.62** — PFS-Risiko real; jeder neue MCP-Tool-Handler der ein eigenes Muster einfuehrt erhoehen PFS messbar.

## When To Use

- Du registrierst ein neues MCP-Tool
- Du aenderst wie ein MCP-Tool-Handler Anfragen verarbeitet oder antwortet
- Du veraenderst das Routing zwischen MCP-Anfragen und `api/`-Funktionen
- Drift meldet PFS fuer `src/drift/serve/`

**Beachte:** MCP-Handler ausserhalb von `serve/` (z.B. `mcp_router_*.py` im Root) werden durch `guard-src-drift` abgedeckt.

## Warum PFS hier entsteht

PFS in `serve/` entsteht durch:
- Neue Tool-Handler die Eingabe-Validierung inline machen statt ueber gemeinsame Schema-Validierung
- Tool-Handler die `api/`-Funktionen unterschiedlich aufrufen (direkt vs. ueber Wrapper)
- Inkonsistente Fehlerantworten: manche Tools geben `{"error": ...}`, andere `{"status": "error", ...}`
- Tool-Metadaten (Name, Beschreibung, Schema) an verschiedenen Stellen definiert

## Core Rules

1. **Alle MCP-Tools folgen demselben Registrierungsmuster** — Tool-Name, Input-Schema und Handler-Funktion werden einheitlich ueber denselben Registrierungs-Mechanismus definiert. Kein Ad-hoc-Tool ausserhalb des Katalogs.

2. **Tool-Handler delegieren an `api/`** — ein MCP-Tool-Handler parst Eingabe, ruft die entsprechende `api.function()` auf und gibt das Ergebnis zurueck. Keine Business-Logik direkt im Handler.

3. **Einheitliches Fehlerformat** — alle Tool-Handler geben bei Fehler `{"status": "error", "message": ..., "agent_instruction": ...}` zurueck. Kein alternatives Format.

4. **`mcp_catalog.py` ist die einzige Tool-Definition** — Tool-Metadaten (was ein Tool tut, welche Parameter es hat) stehen in `mcp_catalog.py`. Keine Beschreibungen im Handler-Code.

5. **Neue Tools benoetigen Schema-Test** — jedes neue MCP-Tool braucht einen Test der sicherstellt, dass das Input-Schema gueltig ist (kein `dict`-Typ, nur `Any` mit Field-Beschreibung).

## Iron Law

> **Kein MCP-Tool-Parameter mit Typ `dict` im Schema.** MCP-Tool-Katalog-Tests lehnen `dict`-Parameter ab. Verwende `Any` mit expliziter Field-Beschreibung.

## Review Checklist

- [ ] Neues Tool ist im zentralen Tool-Katalog (`mcp_catalog.py`) registriert
- [ ] Tool-Handler delegiert an `api/`-Funktion, keine Inline-Logik
- [ ] Fehlerantwort folgt `{"status": "error", "message": ..., "agent_instruction": ...}`
- [ ] Kein `dict`-Typ im Input-Schema (verwende `Any`)
- [ ] Schema-Test fuer neues Tool vorhanden
- [ ] `drift nudge` zeigt `safe_to_commit: true`
- [ ] Keine neuen PFS-Findings in `src/drift/serve/`

## References

- [src/drift/mcp_catalog.py](../../../src/drift/mcp_catalog.py) — MCP-Tool-Katalog und Metadaten
- [src/drift/mcp_server.py](../../../src/drift/mcp_server.py) — MCP-Server-Einstiegspunkt
- [src/drift/api/](../../../src/drift/api/) — Von Tools aufzurufende API-Funktionen
- [DEVELOPER.md](../../DEVELOPER.md)

---
id: ADR-026
status: proposed
date: 2026-04-08
supersedes:
---

# ADR-026: A2A Agent Card und HTTP-Serve-Endpunkt

## Kontext

Drift kommuniziert aktuell ausschließlich über stdio (MCP-Protokoll) und CLI. In Multi-Agenten-Systemen, die dem A2A-Standard (Agent-to-Agent Protocol v1.0) folgen, ist ein standardisiertes Discovery-Manifest (`/.well-known/agent-card.json`) erforderlich, damit Orchestratoren Drift automatisch erkennen und kontaktieren können. Ohne HTTP-Endpunkt ist kein A2A-Discovery möglich.

## Entscheidung

1. **Neuer optionaler HTTP-Server** via `drift serve` CLI-Subcommand.  
   Framework: FastAPI + uvicorn als optionale Dependencies (`pip install drift-analyzer[serve]`).

2. **Agent Card** unter `GET /.well-known/agent-card.json` nach A2A v1.0.  
   Exponiert 8 Kern-Analyse-Skills: scan, diff, explain, fix_plan, validate, nudge, brief, negative_context.

3. **A2A JSON-RPC 2.0 Endpunkt** unter `POST /a2a/v1`.  
   Skill-Dispatch via `skillId` in message metadata oder `skill`-Feld im data-Part.

4. **Security-Defaults**: Host `127.0.0.1` (localhost-only), kein Auth in v1.  
   Netzwerk-Exposure nur via explizitem `--host 0.0.0.0`.

5. **Kein Streaming** in v1 (`capabilities.streaming: false`).

### Was explizit nicht getan wird

- Session-Management- und Task-Queue-Tools (9 von 17 MCP-Tools) werden nicht als A2A-Skills exponiert.
- Kein Authentifizierungsmechanismus in v1 — Risk wird im STRIDE-Modell dokumentiert.
- Kein A2A Push-Notification-Support.
- Kein automatischer HTTPS/TLS — wird dem Deployment (Reverse Proxy) überlassen.

## Begründung

### Warum FastAPI + uvicorn (statt stdlib http.server)

- Typed request/response-Modelle via Pydantic (bereits Core-Dependency)
- OpenAPI-Schema erhalten Nutzer gratis
- FastAPI `TestClient` ermöglicht synchrone Tests ohne laufenden Server
- stdlib `http.server` bietet kein Typed Schema, keine async-Unterstützung, keine Middleware

### Warum JSON-RPC statt REST pro Skill

- A2A v1.0 spezifiziert JSON-RPC 2.0 als primäres Protokoll-Binding
- Ein einzelner `/a2a/v1`-Endpunkt mit Skill-Dispatch ist A2A-konform
- Separate REST-Routen pro Skill wären nicht A2A-kompatibel

### Warum nur 8 von 17 Tools

- Die 8 Kern-Analyse-Tools sind für Orchestratoren relevant (stateless Analyse)
- Session- und Task-Queue-Tools (9 weitere) sind MCP-spezifische Workflow-Hilfen, die im A2A-Kontext keinen Mehrwert bieten
- Erweiterbar in v2 falls Bedarf entsteht

## Konsequenzen

- **Neue optionale Dependencies**: `fastapi>=0.110.0,<1.0` und `uvicorn[standard]>=0.28.0` im `[serve]`-Extra.
- **Neuer Trust Boundary**: HTTP-Clients können über Netzwerk auf Drift-Analyse zugreifen. Default localhost-only mitigiert Remote-Exposure.
- **Repo-Path im Request**: A2A-Handler müssen Pfad-Validierung durchführen (Path-Traversal-Schutz).
- **STRIDE + Risk Register**: Pflicht-Updates unter `audit_results/` (Policy §18).
- **Kein Breaking Change**: Bestehende CLI und MCP-Nutzung bleiben unverändert; `serve` ist rein additiv.

## Validierung

- [ ] `pytest tests/test_a2a_serve.py` — alle Tests grün (Agent Card, JSON-RPC Dispatch, Fehlercodes)
- [ ] `curl http://localhost:8080/.well-known/agent-card.json` liefert valides A2A v1.0 JSON
- [ ] A2A JSON-RPC POST mit `scan`-Skill liefert korrekte Analyse-Antwort
- [ ] `mypy src/drift/serve/` + `ruff check` fehlerfrei
- [ ] `drift serve` ohne installiertes FastAPI zeigt Installations-Hinweis

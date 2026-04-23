# ADR-045: MCP HTTP/SSE Transport

- **Status:** proposed
- **Datum:** 2026-04-10
- **Autor:** Agent (Entwurf)
- **Betrifft:** `src/drift/mcp_server.py`, `src/drift/commands/mcp.py`

## Kontext

Drift's MCP-Server nutzt aktuell ausschließlich stdio-Transport. Das funktioniert für VS Code (lokale Integration), ist aber limitierend für:

1. **Remote-Agenten**: Cloud-basierte Coding-Agenten (Devin, Cursor remote, GitHub Codespaces) können keinen lokalen stdio-Prozess spawnen.
2. **Multi-Client**: stdio ist 1:1 — nur ein Agent-Client gleichzeitig.
3. **Web-UIs**: Browser-basierte Dashboards oder Chat-Interfaces benötigen HTTP.
4. **CI-Integration**: Langlebiger Server statt pro-Aufruf-Startup.

Die MCP-Spezifikation definiert HTTP/SSE als zweiten Standard-Transport neben stdio.

## Entscheidung

### Transport-Erweiterung

```
drift mcp --serve --transport http --port 3333
drift mcp --serve --transport stdio   # default (bestehend)
```

### Security-Modell

| Aspekt | Entscheidung | Begründung |
|--------|-------------|------------|
| **Bind-Adresse** | `127.0.0.1` (localhost-only) Default | Kein Netzwerk-Exposure ohne explizites Opt-in |
| **Network-Modus** | `--bind 0.0.0.0` nur mit `--allow-network` Flag | Opt-in für Remote-Szenarien |
| **Authentifizierung** | Bearer-Token, beim Start generiert und auf stderr angezeigt | Einfach, kein Key-Management nötig |
| **Token-Rotation** | Neues Token bei jedem Server-Start | Keine persistenten Secrets |
| **CORS** | Nur `localhost` Origins per Default, `--cors-origin` Flag | XSS-Schutz |
| **Rate-Limiting** | 60 req/min Default, konfigurierbar via `--rate-limit` | DoS-Schutz |
| **TLS** | Nicht in v1, da localhost-only; empfohlen wenn `--allow-network` | Roadmap-Item |

### STRIDE-Analyse (Trust Boundary: HTTP-Endpunkt)

| Bedrohung | Risiko | Mitigation |
|-----------|--------|-----------|
| **S**poofing | Mittel — unauthentifizierte Requests | Bearer-Token bei jedem Request |
| **T**ampering | Niedrig — localhost, keine Mutation | Read-only Analyse-API; kein Schreib-Zugriff auf Dateisystem |
| **R**epudiation | Niedrig | Request-Logging mit Timestamps |
| **I**nformation Disclosure | Mittel — Analyse-Ergebnisse enthalten Codepfade | Token-Auth verhindert unautorisierten Zugriff |
| **D**enial of Service | Mittel — teure Analyse-Operationen | Rate-Limiting + Request-Timeout |
| **E**levation of Privilege | Niedrig — Server läuft als User-Prozess | Kein Root, kein Schreib-Zugriff |

### Technische Umsetzung

1. **MCP SDK nutzen**: `mcp` Python-SDK unterstützt bereits `sse` Transport-Modus. Kein eigener HTTP-Server nötig.
2. **Middleware-Chain**: Auth-Check → Rate-Limit → CORS → MCP-Handler
3. **CLI-Flags**:
   - `--transport {stdio,http}` (default: stdio)
   - `--port N` (default: 3333)
   - `--bind ADDR` (default: 127.0.0.1)
   - `--allow-network` (bindet auf 0.0.0.0)
   - `--cors-origin URL` (default: http://localhost:*)
   - `--rate-limit N` (default: 60)
4. **Token-Management**: `secrets.token_urlsafe(32)` beim Start, ausgegeben auf stderr

### Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `src/drift/mcp_server.py` | Transport-Abstraktion, Auth-Middleware |
| `src/drift/commands/mcp.py` | Neue CLI-Flags |
| `audit_results/stride_threat_model.md` | HTTP Trust Boundary dokumentieren |
| `audit_results/risk_register.md` | HTTP-spezifische Risiken |

## Begründung

- HTTP/SSE ist der MCP-Standard für nicht-lokale Szenarien
- localhost-only Default eliminiert die größten Security-Risiken
- Token-Auth ist minimal aber effektiv für Developer-Tooling
- Rate-Limiting schützt vor versehentlichen Endlos-Loops durch Agenten

## Konsequenzen

### Positiv
- Drift ist nutzbar für Cloud-IDEs, Remote-Agenten und Web-Dashboards
- Multi-Client-Zugriff möglich (mehrere Agenten parallel)
- Kompatibel mit MCP-HTTP-Clients (Cursor, Continue.dev, etc.)

### Negativ
- Neue Angriffsfläche (HTTP-Endpunkt), mitigiert durch localhost + Token
- Zusätzliche Dependency auf ASGI-Server (falls nicht im MCP-SDK enthalten)
- Audit-Pflicht bei jeder Änderung am HTTP-Transport (STRIDE, Risk Register)

### Neutral
- stdio bleibt Default — kein Breaking Change

## Validierung

- Funktional: `drift mcp --serve --transport http --port 3333` startet, Token wird angezeigt
- Security: Request ohne Token → 401; Request mit Token → 200
- Rate-Limit: 61. Request innerhalb 1 Minute → 429
- Localhost: Externe Verbindung ohne `--allow-network` → Connection refused

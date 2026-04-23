---
name: "Drift Feature 08 — VS Code Extension (Beta)"
description: "Baut den bestehenden extensions/vscode-drift/-Ordner zur funktionsfähigen Beta aus: MCP-Client, Inline-Finding-Overlay, Status-Bar-Score, Code-Action für drift_nudge nach Edit. Keine eigene Analyse-Logik. Voraussetzung: ADR-084 accepted Option C und Item 05 (Cold-Start) abgeschlossen."
---

# Drift Feature 08 — VS Code Extension (Beta)

End-to-End-Implementierung von Item 08. Baut
`extensions/vscode-drift/` zu einer installierbaren Beta aus, die
gegen den lokalen Drift-MCP-Server läuft.

> **Pflicht:** Drift Policy Gate. ADR-084 `accepted` (Option C).
> **Zusätzlich:** Item 05 (Cold-Start) muss abgeschlossen sein,
> sonst hat die Extension keinen akzeptablen IDE-UX-Eindruck.

## Relevante Referenzen

- **Backlog-Item:** [`master-backlog/08-vscode-extension-beta.md`](../../master-backlog/08-vscode-extension-beta.md)
- **Code-Basis:** `extensions/vscode-drift/` (bestehendes Scaffold)
- **MCP-Server:** `src/drift/mcp_server.py`, `.vscode/mcp.json`
- **MCP-Tools:** `src/drift/mcp_router_*.py` (Tool-Signaturen)
- **ADR-Workflow:** `.github/skills/drift-adr-workflow/SKILL.md`

## Arbeitsmodus

- **Dünne Schicht.** Extension enthält keine Analyse-Logik.
  Alles läuft via MCP gegen den lokalen Drift-Server.
- **TypeScript.** Extension-Code liegt vollständig in
  `extensions/vscode-drift/`, nicht in `src/drift/`.
- **Versions-Matrix dokumentiert.** Welche Drift-Versionen werden
  vom Extension-MCP-Client unterstützt?

## Ziel

Installierbare VS-Code-Extension-Beta mit:

- Status-Bar-Item zeigt aktuellen Drift-Score
- Inline-Diagnostics (Squigglies) für Findings aus `drift_scan`
- Code-Action "Drift: Nudge this file" ruft `drift_nudge` nach
  Edit und zeigt Richtungsanzeige (improving / stable / degrading)
- Befehl "Drift: Analyze Workspace" ruft `drift_scan` auf

Kein Marketplace-Release in diesem Prompt. Nur lokaler Beta-
Installationspfad via `.vsix`.

## Erfolgskriterien

- Sub-ADR `docs/decisions/ADR-NNN-vscode-extension-architecture.md`
  `proposed` mit Architektur-Entscheidung:
  - MCP-Client-Lib-Wahl (offizielles SDK oder eigener Wrapper)
  - Diagnostic-Mapping Drift-Severity → VS-Code-Severity
  - Mono-Repo (hier) vs. separates Repo — hier bleiben mit
    Begründung
- `extensions/vscode-drift/package.json` vollständig:
  - `name`, `displayName`, `publisher: mick-gsk`
  - `engines.vscode`, `activationEvents`
  - `contributes.commands`, `contributes.configuration`
  - Skripte für `vsce package`
- TypeScript-Quellcode:
  - `src/extension.ts` Activate/Deactivate
  - `src/mcpClient.ts` (MCP-Client-Wrapper)
  - `src/statusBar.ts`
  - `src/diagnostics.ts`
  - `src/commands.ts`
- Tests unter `extensions/vscode-drift/test/` mit
  `@vscode/test-electron`:
  - Activate-Smoke
  - Diagnostic-Roundtrip gegen einen Fixture-MCP-Mock
- README unter `extensions/vscode-drift/README.md`:
  - Installationsweg via `.vsix`
  - Konfigurationsoptionen
  - Bekannte Limitierungen
- CI-Workflow-Snippet (oder Hinweis in `docs/`) für
  `vsce package`-Build.
- Feature-Evidence `benchmark_results/vX.Y.Z_feature_evidence.json`
  — für diese Extension eher qualitativ: Screenshots-Pfade,
  manuelle Smoke-Test-Ergebnisse.
- Conventional Commit `feat(vscode): beta extension with
  MCP-backed diagnostics and nudge action` + `Decision: ADR-NNN`.

## Phasen

### Phase 1 — Sub-ADR

- Template: `docs/decisions/templates/adr-template.md`.
- Architektur-Entscheidungen begründet (MCP-Client-Wahl,
  Mono-Repo-Entscheidung, Versions-Matrix).

### Phase 2 — package.json und Manifest

- `extensions/vscode-drift/package.json` vollständig.
- `tsconfig.json`, `.vscodeignore`, `.eslintrc` konsistent.

### Phase 3 — MCP-Client-Wrapper

- `src/mcpClient.ts`: dünner Wrapper um offiziellen MCP-Client,
  handhabt Connection zu lokalem Drift-Server
  (stdio, Config via `.vscode/mcp.json`-Logik).
- Reconnect-Logik, klare Error-Messages bei fehlender Drift-
  Installation.

### Phase 4 — Status-Bar

- `src/statusBar.ts`: Zeigt Score, aktualisiert bei
  File-Save-Event.
- Klick öffnet "Drift: Analyze Workspace"-Command.

### Phase 5 — Diagnostics

- `src/diagnostics.ts`: mapped `drift_scan`-Findings auf
  `vscode.Diagnostic[]`.
- Severity-Mapping konsistent mit `src/drift/output/`-Konvention.

### Phase 6 — Commands und Code-Actions

- `drift.analyzeWorkspace`: ruft `drift_scan` via MCP
- `drift.nudgeCurrentFile`: ruft `drift_nudge` auf aktive Datei,
  Notification mit Direction-Tag
- Code-Action-Provider (optional in Beta): Quick-Fix-Stub,
  der auf Drift-Fix-Plan verweist

### Phase 7 — Tests

- `@vscode/test-electron`-basierte Testsuite.
- Mock-MCP-Server für CI (kein echter Drift-Call in Tests).

### Phase 8 — Dokumentation

- `extensions/vscode-drift/README.md` vollständig.
- Ergänzung in `docs/` (falls Docs-Site vorhanden) mit Screenshot-
  Galerie und Installationsanleitung.

### Phase 9 — Package-Build

- Lokaler `vsce package`-Lauf muss erfolgreich sein.
- `.vsix` in `work_artifacts/feature_08_<YYYY-MM-DD>/` ablegen
  (nicht committen).

### Phase 10 — Audit-Update (bedingt)

- Extension ist externes Interface zu MCP — STRIDE prüfen:
  neue Angriffsflächen (unsigned `.vsix`, MCP-Command-Injection
  via Extension-Input).
- Falls relevant: `audit_results/stride_threat_model.md` +
  `risk_register.md` aktualisieren.

### Phase 11 — Commit

- CHANGELOG-Eintrag.
- Conventional Commit + Decision-Trailer.
- Push-Gates lokal grün.

## Artefakte

```
work_artifacts/feature_08_<YYYY-MM-DD>/
    run.md
    drift-vscode-<version>.vsix               # lokal, nicht committed
docs/decisions/ADR-NNN-vscode-extension-architecture.md
extensions/vscode-drift/
    package.json
    tsconfig.json
    src/extension.ts
    src/mcpClient.ts
    src/statusBar.ts
    src/diagnostics.ts
    src/commands.ts
    test/*.test.ts
    README.md
benchmark_results/vX.Y.Z_feature_evidence.json
audit_results/stride_threat_model.md          # bedingt
audit_results/risk_register.md                # bedingt
CHANGELOG.md
```

## Nicht Teil dieses Prompts

- Kein Marketplace-Release (kein `vsce publish`).
- Keine eigene Analyse-Logik in der Extension.
- Keine Telemetrie in der Extension — Drift-Telemetrie via MCP
  respektiert, POLICY §19 gilt.
- Keine Sprach-Versprechen außerhalb dessen, was `drift_scan`
  heute liefert.
- Kein Push, keine Sub-ADR-Akzeptanz durch Agent.

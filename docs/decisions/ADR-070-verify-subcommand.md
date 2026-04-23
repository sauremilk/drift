---
id: ADR-070
status: proposed
date: 2026-04-13
supersedes:
---

# ADR-070: `drift verify` — Post-Edit Verification Subcommand

## Kontext

LLM-generierter Code wird zunehmend ohne manuelle Review in Codebases integriert.
Agentic Workflows (Copilot, Cursor, Claude Code) erzeugen Edits, die strukturelle
Kohärenz implizit voraussetzen, aber nicht deterministisch verifizieren.

Bestehende drift-Werkzeuge (nudge, shadow_verify, check, diff) decken Teilaspekte ab:
- `nudge` → inkrementell, file-lokal, kein binäres Pass/Fail
- `shadow_verify` → scope-bounded full re-scan, aber kein CLI-Command
- `check` → CI-Gate auf Severity-Threshold, aber nicht diff-basiert
- `diff` → Change-focused, aber kein explizites Pass/Fail-Envelope

Keines liefert ein **einziges, binäres, CI-integrierbares Verdict** für die Frage:
"Hat dieser Edit die strukturelle Kohärenz verschlechtert?"

## Entscheidung

Neuer CLI-Subcommand `drift verify` und korrespondierendes MCP-Tool `drift_verify`.

**Was getan wird:**
- Neuer Subcommand `drift verify` mit Pass/Fail-Envelope (JSON + Rich)
- Neue API-Funktion `drift.api.verify.verify()` als Wrapper um `shadow_verify()`
- Neues MCP-Tool `drift_verify` mit ADR-024-konformem Routing
- VerifyResult-Schema im Output-Contract

**Was explizit nicht getan wird:**
- Kein neues Signal
- Keine Scoring-Änderung
- shadow_verify() wird nicht verändert, nur gewrappt
- check-Command wird nicht geändert

**Alternative: Flag an `check` statt eigenständiger Command**
Verworfen: `check` hat CI-spezifische Semantik (diff-ref, severity-gate);
`verify` hat edit-spezifische Semantik (scope-files, pass/fail auf Delta).
Ein kombinierter Command würde beide Anwendungsfälle vermischen.

## VerifyResult-Schema

```
pass: boolean             — true wenn keine blocking findings + Delta <= 0
blocking_reasons: []      — strukturierte Gründe (signal, file, severity, title)
findings_introduced: []   — neue Findings seit Referenz (kompakt)
findings_resolved: []     — behobene Findings (kompakt)
score_before: float       — Score vor Edit
score_after: float        — Score nach Edit
score_delta: float        — Differenz (positiv = Regression)
direction: string         — improving/stable/degrading
ref: string               — Git-Ref oder Baseline
elapsed_ms: int
```

## CLI-Flags

```
--repo, -r          Repository-Root (default: ".")
--ref               Git-Ref zum Vergleich (default: HEAD~1)
--uncommitted       Analyze Working-Tree vs. HEAD
--staged-only       Nur staged Changes
--fail-on           Severity-Threshold (default: high)
--baseline          Baseline-File für Fingerprint-Vergleich
--format, -f        Output-Format (json/rich, default: rich)
--exit-zero         Immer Exit-Code 0
--output, -o        Output-File
--scope             Comma-separated File-Patterns
```

## Exit-Codes

- 0: PASS (oder --exit-zero)
- 1: FAIL (findings above threshold oder score degradation)

## Begründung

1. **Einziger fehlender Baustein:** drift hat scan, nudge, diff, check — aber kein
   "verify this edit" Command mit binärem Verdict
2. **CI-Gate für LLM-Code:** `drift verify --fail-on high` als Pipeline-Step
3. **MCP-native:** Agents rufen `drift_verify` nach Code-Generation auf
4. **Keine neue Infra:** Wraps `shadow_verify()`, nutzt bestehende Scoring-Pipeline
5. **Strategische Positionierung:** drift als "deterministic counterpart to LLMs"

## Konsequenzen

- Neuer CLI-Command in help-output und Docs
- MCP-Katalog wächst um 1 Tool
- FMEA: Neuer Fehlermodus "verify false-pass" (leerer Scope, stale Baseline)
- Fault Tree: FN-Chain für Ref-Mismatch und Scope-Lücke
- Risk Register: "verify-bypass durch leeren Scope"

## Validierung

1. `drift verify --repo . --ref HEAD~1 --format json` auf eigenem Repo → PASS
2. `drift verify --repo examples/demo-project --fail-on medium` → FAIL (Exit 1)
3. MCP-Katalog-Test: `drift_verify` in Katalog + Schema-konform
4. Precision: 0 false-pass auf Ground-Truth-Fixtures
5. §10 Lernzyklus: Ergebnis nach 30-Tage-Nutzung bewerten

# ADR-080: Strict MCP Guardrails by Default (v2.25.0)

- Status: proposed
- Date: 2025-01-XX
- Decision-Maker: Mick Gottschalk
- Supersedes: none
- Related: ADR-022 (MCP session orchestration), ADR-063 (strict guardrails opt-in)

## Kontext

Die MCP-Orchestrierung hatte bis v2.24.0 einen **Opt-in-Strict-Mode** (`agent.strict_guardrails: true`).
In der Vibe-Coding-Gap-Analyse (L1–L12) zeigte sich: Agenten ignorieren Empfehlungen
(nudge.direction, scope-warnings, brief-Staleness), wenn sie nicht hart geblockt werden.
Drift verbleibt damit bei „Reviewer neben dem Agenten" statt „enforcement layer".

Die Analyse quantifizierte drei konkrete Lücken, die nur durch aktive Gates geschlossen
werden können:

- **L7 (revert_recommended):** `safe_to_commit=False` war nur advisory; Agenten konnten
  commits trotz REVERT-Empfehlung durchdrücken.
- **L8 (scope confidence):** Niedrige Scope-Konfidenz erzeugte nur eine Warnung; kein
  Zwang zur Rückfrage an den User.
- **L11 (stale brief):** Einmal geladener Brief blieb auch bei messbarem Baseline-Drift
  oder vielen Zwischenschritten als „frisch" gültig.

## Entscheidung

Ab v2.25.0 ist `agent.strict_guardrails` **standardmäßig `true`**. Opt-out bleibt möglich
per `strict_guardrails: false` in `drift.yaml`.

Zusätzlich werden drei neue Guardrail-Regeln aktiv:

| Regel   | Tool                          | Auslöser |
|---------|-------------------------------|----------|
| SG-005a | `drift_fix_apply`             | Brief ist stale (score-delta > 0.1, > 20 tool calls, oder > 30 min) |
| SG-006a | `drift_patch_begin`           | identisch zu SG-005a |
| SG-007  | `drift_fix_apply` / `drift_patch_begin` | letzter Brief hat `scope_gate.action_required=ask_user` gesetzt |

Außerdem wird `revert_recommended` in `drift_nudge` verschärft:

- `revert_recommended = not safe_to_commit AND (direction == "degrading" OR parse_failures > 0 OR git_detection_failed)`
- Ein neuer Pre-Commit-Hook `scripts/nudge_gate.py` blockt Commits, wenn der zuletzt
  geschriebene `.drift-cache/last_nudge.json` einen REVERT empfohlen hat und die
  betroffenen Dateien unverändert staged sind.

## Alternativen

1. **Opt-in bleiben, Doku verstärken.** Verworfen — Gap-Analyse zeigte, dass passive
   Empfehlungen wirkungslos sind.
2. **Nur Brief-Staleness, nicht Scope-Gate.** Verworfen — Scope-Fehler erzeugen die
   gefährlichsten Out-of-Scope-Edits und rechtfertigen einen eigenen Gate.
3. **Globale Env-Variable `DRIFT_STRICT=0` statt Config-Feld.** Verworfen — Config
   ist versionierbar und pro Repo konfigurierbar; Env führt zu „funktioniert lokal,
   nicht in CI"-Problemen.

## Konsequenzen

### Positiv
- Scope- und Brief-Freshness werden deterministisch erzwungen, nicht empfohlen.
- Agent-Fehlerpfade (scope-Misslesung, stale brief) werden vor dem Edit geblockt,
  nicht erst nach einem fehlerhaften Commit entdeckt.
- Pre-Commit-Gate macht REVERT-Empfehlungen zu einem harten Integrationsblocker.

### Negativ / Breaking
- Repositories ohne explizite `strict_guardrails: false` erhalten beim Upgrade neue
  Block-Verhalten. CHANGELOG und Release Notes markieren dies als „BREAKING behavior".
- Bestehende Agenten-Workflows, die sich auf advisory-only verlassen, müssen entweder
  SG-005a/SG-006a/SG-007 erfüllen oder explizit opt-out setzen.

### Neutral
- Bestehende SG-001..SG-006 bleiben unverändert.
- `drift.schema.json` wird regeneriert; der Schema-Test `test_schema_matches_live_model`
  validiert die Synchronität.

## Rollback

- `strict_guardrails: false` in `drift.yaml` stellt v2.24.0-Verhalten wieder her.
- `DRIFT_SKIP_NUDGE_GATE=1` deaktiviert den Pre-Commit-Hook für einzelne Commits.

## Nachweise

- `benchmark_results/v2.25.0_feature_evidence.json`
- `tests/test_mcp_orchestration_coverage.py::TestScopeGateAndStalenessRules`
- `tests/test_nudge_gate.py`
- `tests/test_nudge.py` (revert_recommended Matrix)
- `audit_results/risk_register.md` (SG-007, SG-005a, nudge_gate entries)

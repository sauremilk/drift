# Session-Handover-Contract (ADR-079)

Dieses Partial ist Single Source of Truth für das von `drift_session_end`
validierte Artefakt-Schema. Agenten und Skills referenzieren es — sie
duplizieren es nicht.

## Geltungsbereich

Gilt ausschliesslich für `work_artifacts/session_<id8>.md` am Ende einer
MCP-Session. Evidence-JSON folgt
[drift-evidence-artifact-authoring](../../skills/drift-evidence-artifact-authoring/SKILL.md),
ADR-Drafts folgen
[drift-adr-workflow](../../skills/drift-adr-workflow/SKILL.md).

## Dateiname

```
work_artifacts/session_<id8>.md
```

- `<id8>` = erste 8 Zeichen der `session_id` (wie im MCP-Trace und in
  Logausgaben verwendet).
- Keine zusätzlichen Suffixe, keine Zeitstempel im Namen.

## Frontmatter (YAML, Pflicht)

```yaml
---
session_id: "<full-uuid>"
started_at: "2026-04-21T09:15:30Z"
ended_at: "2026-04-21T09:47:12Z"
duration_seconds: 1902
tool_calls: 42
tasks_completed: 5
tasks_remaining: 0
findings_delta: -12
change_class: "signal"        # signal | architecture | fix | docs | chore
repo_path: "C:/Users/mickg/PWBS/drift"
git_head_at_plan: "a1b2c3d4"
git_head_at_end: "e5f6a7b8"
adr_refs: ["ADR-079"]         # leer erlaubt nur bei docs/chore
evidence_files:               # leer erlaubt nur bei docs/chore
  - "benchmark_results/v2.25.0_session_handover_gate_feature_evidence.json"
audit_artifacts_updated:      # mind. 1 Eintrag bei change_class=signal
  - "audit_results/fmea_matrix.md"
  - "audit_results/risk_register.md"
---
```

Die markierten Felder werden vom Server gegen `SessionManager`-State
verifiziert. Mismatch (z.B. `session_id` aus Fremdsession, `tasks_completed`
abweichend) = Shape-Error.

## Pflicht-Sektionen (Markdown)

Jede Sektion muss nicht-leer sein (Whitespace-only = Fehler). Reihenfolge ist
verbindlich.

### `## Scope`

Was wurde in dieser Session bearbeitet und was explizit nicht. Mindestens 2
Sätze oder 2 Bullet-Items. Touched files werden als Code-Block gelistet.

### `## Ergebnisse`

Konkrete Outcomes: verschobene Findings, neue Tests, geänderte Heuristiken,
getroffene Entscheidungen. Prosa erlaubt, aber mindestens 1 konkrete Zahl oder
Pfadreferenz.

### `## Offene Enden`

Was noch nicht fertig ist und warum. Jedes Item: was offen + warum offen +
welcher Folge-Agent/Schritt es übernimmt. Leerer Abschnitt nur mit expliziter
Formulierung `Keine offenen Enden.` zulässig.

### `## Next-Agent-Einstieg`

Der deterministische Einstiegspunkt für den nächsten Agent. Muss enthalten:

1. Einstiegs-Tool-Call als Code-Block (z.B. `drift_session_start(...)`).
2. Relevante Pfade (Dateien, ADR, Evidence).
3. Erwartetes Abbruchkriterium oder Abnahme-Check.

### `## Evidenz`

Direkte Links auf Evidence-JSON, ADR, Audit-Updates. Keine freie Prosa.

## Placeholder-Denylist (L3)

Der Validator lehnt folgende Tokens ab (case-insensitive, Wort-Grenze):

- Struktur-Platzhalter: `TODO`, `FIXME`, `XXX`, `TBD`, `???`, `<N>`, `<NNN>`
- Prosa-Platzhalter: `lorem`, `ipsum`
- Namens-Platzhalter: `foo`, `bar`, `baz` (in Überschriften/Frontmatter)
- Leere Bullet-Items (`- ` ohne Text)
- Nur-Whitespace-Sektionen
- ADR-Kontext mit weniger als 120 Zeichen substantiellem Text

Wörter in Codeblöcken (```…```) sind ausgenommen, wenn sie nachweislich Teil
eines echten Beispiels sind (z.B. `TODO`-Kommentar in echtem Snippet). Die
Regex-Klasse „echtes Beispiel" ist ein ```-Block mit mindestens 3 Zeilen.

## Beispiel-Minimal (docs-Session)

```markdown
---
session_id: "0f23a1c4-...-..."
started_at: "2026-04-21T09:15:30Z"
ended_at: "2026-04-21T09:25:00Z"
duration_seconds: 570
tool_calls: 6
tasks_completed: 0
tasks_remaining: 0
findings_delta: 0
change_class: "docs"
repo_path: "C:/Users/mickg/PWBS/drift"
git_head_at_plan: "a1b2c3d4"
git_head_at_end: "a1b2c3d4"
adr_refs: []
evidence_files: []
audit_artifacts_updated: []
---

## Scope

Überarbeitung von `docs/STUDY.md` Abschnitt „Signal-Priorisierung". Nicht
berührt: Signal-Code, Fixtures.

## Ergebnisse

2 Abschnitte präzisiert, 1 veraltete Tabelle entfernt. Geänderte Datei:
`docs/STUDY.md`.

## Offene Enden

Keine offenen Enden.

## Next-Agent-Einstieg

```
drift_session_start(path=".", autopilot=true)
```

Kein spezifischer Folge-Task geplant; nächster Agent kann mit regulärem
Fix-Loop starten.

## Evidenz

Kein Evidence-JSON erforderlich (change_class=docs).
```

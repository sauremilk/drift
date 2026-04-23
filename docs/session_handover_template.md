# Session Handover Template

Vollständiges Template für `work_artifacts/session_<id8>.md`.
Vertrag siehe [session-handover-contract](../.github/prompts/_partials/session-handover-contract.md).

Das Template dient als Gerüst. Agenten kopieren es, ersetzen ALLE Platzhalter
durch konkrete Werte und befüllen jede Pflicht-Sektion mit echten Inhalten
aus dem Session-Trace. Kopieren ohne Ersetzen blockt im L3-Validator.

```markdown
---
session_id: "<FULL-UUID>"
started_at: "<ISO-8601-Z>"
ended_at: "<ISO-8601-Z>"
duration_seconds: <INT>
tool_calls: <INT>
tasks_completed: <INT>
tasks_remaining: <INT>
findings_delta: <INT>
change_class: "<signal|architecture|fix|docs|chore>"
repo_path: "<ABSOLUTER-PFAD>"
git_head_at_plan: "<SHORT-SHA>"
git_head_at_end: "<SHORT-SHA>"
adr_refs: []
evidence_files: []
audit_artifacts_updated: []
---

## Scope

<Was wurde bearbeitet? Mindestens 2 Sätze oder 2 Bullet-Items. Nenne explizit,
was NICHT berührt wurde.>

Berührte Dateien:

```
<file1>
<file2>
```

## Ergebnisse

<Konkrete Outcomes mit Zahlen oder Pfaden. Was wurde messbar besser?>

## Offene Enden

<Was ist noch nicht fertig? Pro Item: was offen + warum + wer/was übernimmt.
Wenn wirklich nichts offen ist, schreibe: "Keine offenen Enden.">

## Next-Agent-Einstieg

1. Startbefehl:

```
<drift_session_start(...) oder anderer konkreter Einstieg>
```

2. Relevante Pfade:

- <pfad1>
- <pfad2>

3. Abnahmekriterium:

<Wann ist der Folge-Task fertig?>

## Evidenz

- Evidence: <benchmark_results/v*.json | "n/a (change_class=docs)">
- ADR: <docs/decisions/ADR-*.md | "n/a">
- Audit-Updates: <audit_results/*.md | "n/a">
```

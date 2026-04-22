---
description: "Kompakte Task-zu-Gate Kurzanleitung fuer Drift-Agenten. Verwenden fuer schnellen Einstieg bei feat, fix, signal, chore, prompt und review Aufgaben."
---

# Drift Agent Quickref

Diese Datei ist eine kompakte Einstiegshilfe. Sie ersetzt nicht die autoritativen Quellen:
- `POLICY.md`
- `.github/instructions/drift-policy.instructions.md`
- `.github/instructions/drift-push-gates.instructions.md`

## Task-Typ zu Pflicht-Checkliste

| Task-Typ | Aktive Gates | Pflichtdateien/Pflichtartefakte | Empfohlene Startbefehle |
|---|---|---|---|
| `feat:` | 2, 3, 6, 7*, 8 | `tests/**`, `benchmark_results/vX.Y.Z_*_feature_evidence.json`, `CHANGELOG.md`, `docs/STUDY.md`, bei Signal/Ingestion/Output auch Audit-Artefakte | `make feat-start`, danach `make check` |
| `fix:` | 3, 6*, 7*, 8 | `CHANGELOG.md`, bei API-Docs Diff ggf. Docstring-Diff, bei Signal/Ingestion/Output Audit-Artefakte | `make fix-start`, danach `make test-fast` |
| Signal-/Scoring-Arbeit | 2, 3, 7, 8 | Tests + Fixtures, Evidence, `CHANGELOG.md`, Audit-Artefakte (`audit_results/*`), ggf. ADR | `make feat-start`, dann Risk-Audit aktualisieren |
| `chore:` | 8 (plus ggf. 4/5 bei `pyproject.toml`) | Bei Dependency-Aenderung immer konsistentes Lockfile | `make check` |
| Prompt/Instruction/Skill | Policy-Gate, ggf. 8 | Nur relevante Prompt-/Instruction-Dateien, keine Parallel-Policy | zuerst Policy-Gate, dann gezielter Edit |
| Review/Fix-Loop | Quality-Workflow + 8 | Review-Evidenz, konkrete Findings, anschliessende Re-Verification | `make test-fast` oder `make check` |

`*` Gate 6 gilt nur wenn `src/drift/**` betroffen ist. Gate 7 gilt nur bei Aenderungen an `src/drift/signals/**`, `src/drift/ingestion/**` oder `src/drift/output/**`.

## Schnellregeln

1. Vor jeder Umsetzung zuerst das Drift Policy Gate ausgeben.
2. Bei `feat:` niemals Evidence-Datei manuell erstellen; immer `scripts/generate_feature_evidence.py` verwenden.
3. Bei `feat:` oder `fix:` immer `CHANGELOG.md` aktualisieren.
4. Push-Gates sind bindend; Bypass nur als Notfall und dokumentiert.
5. Fuer unklare Zuordnung immer auf `.github/instructions/drift-context-routing.instructions.md` wechseln.

## Pflicht-Shortcuts: Wann welchen `make`-Befehl aufrufen

Diese Shortcuts sind **verbindlich** — sie sind keine Option, sondern Teil des Standard-Workflows.

| Workflow-Moment | Pflicht-Befehl | Zweck |
|---|---|---|
| Vor dem ersten Edit bei `feat:` | `make feat-start` | Policy-Gate + Baseline-Checks sichtbar machen |
| Vor dem ersten Edit bei `fix:` | `make fix-start` | Policy-Gate + Test-Baseline |
| Gates vorab pruefen (vor Push) | `make gate-check COMMIT_TYPE=feat` | Fehlende Artefakte erkennen, bevor der Hook abbricht |
| Audit-Artefakte pruefen | `make audit-diff` | Zeigt welche `audit_results/`-Dateien bei aktuellen Aenderungen aktualisiert werden muessen |
| CHANGELOG-Snippet erzeugen | `make changelog-entry COMMIT_TYPE=feat MSG='...'` | Formatgerechten Eintrag ausgeben (NIEMALS manuell formattieren) |
| Session-Handover erstellen | `make handover TASK='...'` | Uebergabe-Artefakt in `work_artifacts/` ablegen |
| Verfuegbare Skripte anzeigen | `make catalog` | Katalog aller `scripts/`-Tools mit Kurzbeschreibung |
| Vollstaendige CI-Pruefung | `make check` | Lint + Typecheck + Tests + Self-Analyse |

### Konkrete Ablaeufe nach Aufgabentyp

**`feat:` — neues Feature**
```
make feat-start                          # 1. Gates + Baseline
# ... Implementierung ...
make gate-check COMMIT_TYPE=feat         # 2. Fehlende Artefakte anzeigen
make audit-diff                          # 3. Audit-Pflichten pruefen (falls signals/ingestion/output betroffen)
make changelog-entry COMMIT_TYPE=feat MSG='<Beschreibung>'  # 4. CHANGELOG-Snippet ausgeben
make check                               # 5. Vollstaendiger CI-Check
```

**`fix:` — Bugfix**
```
make fix-start                           # 1. Baseline
# ... Fix ...
make gate-check COMMIT_TYPE=fix          # 2. CHANGELOG + Docstring-Gates pruefen
make changelog-entry COMMIT_TYPE=fix MSG='<Beschreibung>'   # 3. Snippet ausgeben
make test-fast                           # 4. Schneller Test-Check
```

**Signal/Scoring/Ingestion/Output-Aenderung (immer zusaetzlich)**
```
make audit-diff                          # Zeigt FMEA/Risk/STRIDE-Updatepflichten
```

**Session-Abschluss oder Uebergabe**
```
make handover TASK='<was wurde gemacht>'  # Handover-Artefakt anlegen
```

**Unbekanntes Skript gesucht**
```
make catalog                              # Alle scripts/ anzeigen
make catalog ARGS='--search evidence'     # Filtern nach Stichwort
```

## Notfall-Bypasses (nur bewusst und begruendet)

- `DRIFT_SKIP_CHANGELOG=1 git push`
- `DRIFT_SKIP_EVIDENCE_VALIDATION=1 git push`
- `DRIFT_SKIP_HOOKS=1 git push` (Achtung: lokale CI kann weiterlaufen)

Nicht als Default nutzen.

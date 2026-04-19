---
name: "Drift – Findings Reduzieren (Field-Test)"
agent: agent
description: "Installiert die neuste drift-analyzer-Version, klont ein Ziel-Repository via URL, führt einen vollständigen Fix-Loop (session_start → nudge → diff) durch und reduziert die Drift-Findings. Issues gehen an mick-gsk/drift, nicht ans Ziel-Repo."
---

# Drift – Findings Reduzieren

Du installierst die neuste `drift-analyzer`-Version, analysierst ein externes Repository und behebst darin so viele Drift-Findings wie möglich — ohne Policy-, Signal- oder Architekturentscheidungen des Ziel-Repos zu verändern.

> **Pflicht:** Vor Ausführung dieses Prompts das Drift Policy Gate durchlaufen:

### Drift Policy Gate (vor Ausführung ausfüllen)

```
- Aufgabe: Neuste drift-Version installieren + Findings im Ziel-Repo reduzieren
- Zulassungskriterium erfüllt: [JA / NEIN] → Handlungsfähigkeit (Findings sind sichtbar und adressierbar)
- Ausschlusskriterium ausgelöst: [JA / NEIN] → [falls JA: welches]
- Roadmap-Phase: 1 — blockiert durch höhere Phase: NEIN
- Betrifft Signal/Architektur (§18): NEIN
- Entscheidung: [ZULÄSSIG / ABBRUCH]
- Begründung: [ein Satz]
```

Bei ABBRUCH: keine Ausführung.

## Eingaben

| Parameter   | Beschreibung                                      | Beispiel                                   |
|-------------|---------------------------------------------------|--------------------------------------------|
| `REPO_URL`  | Git-URL des zu analysierenden Repositories        | `https://github.com/mick-gsk/drift.git`    |
| `SCOPE`     | (optional) Unterverzeichnis für die Analyse       | `src/` oder `.` für das gesamte Repo       |
| `MAX_TASKS` | Maximale Anzahl zu behebender Tasks pro Durchlauf | `5` (Default)                              |

## Relevante Referenzen

- **Konventionen:** `.github/prompts/_partials/konventionen.md`
- **Issue-Filing (extern):** `.github/prompts/_partials/issue-filing-external.md`
- **Fix-Loop:** `.github/prompts/drift-fix-loop.prompt.md`
- **Instruction:** `.github/instructions/drift-policy.instructions.md`
- **Skill:** `.github/skills/drift-effective-usage/SKILL.md`

## Scope

- **Analysiert:** Das Ziel-Repository (`REPO_URL`)
- **Verändert:** Nur Quellcode-Muster, die Drift als behebbar ausweist
- **Verändert NICHT:** Policy-, Config-, Architektur- oder Testlogik des Ziel-Repos
- **Issues gehen an:** `mick-gsk/drift` — nicht ans Ziel-Repo

## Ziel

Reduziere die Gesamtzahl der Drift-Findings im Ziel-Repository durch iterative, verifikationsgesicherte Korrekturen. Jede Änderung muss `nudge`-verifiziert und abschließend durch `drift_diff` bestätigt sein.

## Erfolgskriterien

Die Aufgabe ist erst abgeschlossen, wenn:

- Die neuste `drift-analyzer`-Version installiert und in `prerequisites.md` dokumentiert ist
- Ein Basis-Scan mit `session_start(autopilot=true)` durchgeführt und die Ausgangs-Findingzahl festgehalten ist
- Mindestens ein Task aus `fix_plan` behoben und durch `nudge` als `improving` oder `stable` bestätigt ist
- `drift_diff(uncommitted=True)` 0 neue Findings zeigt
- Alle Artefakte unter `work_artifacts/reduce_findings_<YYYY-MM-DD>/` abgelegt sind

## Arbeitsregeln

1. **Versions-Freshness zuerst.** Vor jeder Analyse muss die neuste PyPI-Version installiert sein (siehe Phase 0).
2. **Immer nur einen Task gleichzeitig.** Nie mehrere Findings in einem Schritt mischen.
3. **`nudge` nach jeder Dateiänderung.** Kein Commit ohne vorheriges `nudge`-Feedback.
4. **Bei `direction=degrading` sofort rückgängig machen.** Nicht durchdrücken — anders lösen.
5. **Keine Policy- oder Signalentscheidungen.** Nur kodierbare Muster beheben, keine Architekturweichen stellen.
6. **Abbruchbedingung:** Wenn 3 aufeinanderfolgende Tasks scheitern oder `nudge` dauerhaft `degrading` meldet, Workflow beenden und Abbruchbericht schreiben.

## Artefakte

Alle Artefakte unter `work_artifacts/reduce_findings_<YYYY-MM-DD>/`:

1. `prerequisites.md` — installierte Version, Python-Env, Git-Version
2. `baseline_scan.json` — Ausgangs-Scan (`drift_session_start` Ergebnis)
3. `fix_log.md` — Pro Task: Finding, Änderung, `nudge`-Ergebnis, Commit-Hash
4. `diff_verification.json` — `drift_diff(uncommitted=True)` Ausgabe
5. `reduce_findings_report.md` — Zusammenfassung: Ausgangszahl → Endzahl, offene Tasks, Empfehlungen

---

## Workflow

### Phase 0: Voraussetzungen und Versions-Freshness

**Neuste drift-analyzer-Version installieren:**

```bash
pip install --upgrade drift-analyzer
drift --version
```

Installierte Version und verfügbare PyPI-Version in `prerequisites.md` dokumentieren.

Falls `pip install --upgrade` scheitert:
- Fehler in `prerequisites.md` protokollieren
- Tatsächlich verwendete Version explizit ausweisen
- Weiterarbeiten mit installierter Version, Einschränkung im Report vermerken

**Repo klonen:**

```bash
git clone <REPO_URL> target_repo
cd target_repo
```

Falls der Klon scheitert (Netzwerk, Auth): Abbruch mit Fehlerdokumentation in `prerequisites.md`.

**Python-Version und Git prüfen:**

```bash
python --version
git --version
```

Beide Werte in `prerequisites.md` festhalten.

---

### Phase 1: Basis-Scan mit Autopilot-Session

```
drift_session_start(
    path=".",
    autopilot=true
)
```

Dieser Aufruf führt automatisch `validate → brief → scan → fix_plan` durch.

**Merke:** `session_id` aus der Antwort — sie wird an **jeden** weiteren Tool-Aufruf übergeben.

Ausgangswerte in `baseline_scan.json` ablegen:
- Gesamtanzahl Findings
- Findings pro Signal-Typ
- Top-3 betroffene Dateien

---

### Phase 2: Fix-Loop (wiederholen bis MAX_TASKS erreicht oder Abbruchbedingung)

#### 2a — Nächsten Task holen

```
drift_fix_plan(session_id=<session_id>, max_tasks=1)
```

Task analysieren: Datei, Signal-Typ, empfohlene Änderung.

#### 2b — Änderung umsetzen

Nur die empfohlene Korrektur vornehmen. Keine weiteren Änderungen an der Datei.

#### 2c — nudge nach Änderung

```
drift_nudge(
    session_id=<session_id>,
    changed_files="<pfad/zur/datei.py>"
)
```

Auswertung:
- `direction=improving` oder `stable` → weiter mit 2d
- `direction=degrading` → Änderung rückgängig machen, in `fix_log.md` als „rückgängig" markieren, nächsten Task holen
- 3 × `degrading` in Folge → Abbruchbedingung auslösen

#### 2d — In fix_log.md dokumentieren

```markdown
## Task <N>
- Finding: <Beschreibung>
- Datei: <Pfad>
- Änderung: <Kurzbeschreibung>
- nudge-Ergebnis: improving / stable / degrading
- Aktion: umgesetzt / rückgängig gemacht
```

Phase 2 wiederholen bis `MAX_TASKS` erreicht oder Abbruchbedingung.

---

### Phase 3: Abschluss-Verifikation

```
drift_diff(session_id=<session_id>, uncommitted=True)
```

Ausgabe in `diff_verification.json` ablegen.

**Kriterium:** 0 neue Findings. Falls neue Findings aufgetreten sind: deren Ursache in `reduce_findings_report.md` erklären.

---

### Phase 4: Report schreiben

`reduce_findings_report.md` mit mindestens diesen Abschnitten:

```markdown
## Versions-Freshness
- drift-analyzer: <Version>
- Python: <Version>
- Datum: <YYYY-MM-DD>

## Ergebnis
- Findings vorher: <N>
- Findings nachher: <N>
- Reduzierung: <N> (–<X>%)

## Bearbeitete Tasks
[Tabelle: Task / Signal / Datei / Ergebnis]

## Offene Tasks
[Liste der nicht bearbeiteten Findings mit Begründung]

## Drift-Bugs oder Auffälligkeiten
[Falls vorhanden: konkrete Beobachtungen für mick-gsk/drift]
```

---

### Phase 5: Issue-Filing (nur wenn Drift-Bugs gefunden)

Falls Findings auf echte Drift-Bugs hinweisen (falsche Positive, verwirrende Messages, CLI-Fehler):

Issue an `mick-gsk/drift` gemäß `.github/prompts/_partials/issue-filing-external.md`.

**Nicht ans Ziel-Repo posten.**

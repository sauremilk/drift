---
agent: agent
description: "Drift Agent-Workflow-Test: Vollständiger CLI- und Praxis-Test aller aktuell verfügbaren drift-Funktionen gegen das Repo, mit Agent-UX-Bewertung, Sandbox-Workflows und GitHub-Issue-Erstellung."
---

# Drift Agent-Workflow-Test

Du bist ein Coding Agent, der `drift-analyzer` in einem realen Maintainer- und Agenten-Workflow testet. Führe den folgenden Workflow **vollständig** durch und dokumentiere nach jedem Schritt, ob die Antwort fuer dich als Agent **ausreichend, unzureichend oder irrefuehrend** war.

## Ziel

Teste **alle aktuell verfuegbaren CLI-Funktionen** von `drift-analyzer` in einem praxisnahen Workflow und erzeuge am Ende einen strukturierten Ergebnisbericht mit:
- Welche Befehle funktioniert haben
- Welche Befehle unklare oder unbrauchbare Ergebnisse lieferten
- Wo du als Agent in einer Sackgasse gelandet bist
- Welche Befehle fuer reale Maintainer-, CI-, Refactoring- und AI-Integrations-Workflows brauchbar sind
- Konkrete Verbesserungsvorschlaege

## Leitregeln

- Nutze shell- und plattformgerechte Kommandos. Wenn Beispiele POSIX-Syntax enthalten, darfst du sie fuer PowerShell oder die aktuelle Umgebung aequivalent umsetzen.
- Ermittle den aktuellen CLI-Umfang **dynamisch** ueber `drift --help` und `drift <command> --help`. Gehe nie von einer statischen Liste aus.
- **Jeder** gefundene Top-Level-Befehl muss im Bericht erscheinen und einen Status haben: `getestet`, `begruendet uebersprungen` oder `blockiert`.
- Bei Gruppenbefehlen wie `baseline` und `config` musst du auch die relevanten Subcommands inventarisieren und testen.
- Teste schreibende Befehle bevorzugt in einer Sandbox unter `work_artifacts/drift_agent_test_<DATUM>/sandbox/`, damit das echte Repo nicht unnoetig verschmutzt wird.
- Teste nach Moeglichkeit **echte Repo-Szenarien** statt kuenstlicher Mini-Beispiele. Kuenstliche Aenderungen sind nur erlaubt, wenn ein Befehl zwingend einen Diff oder ein leeres Repo benoetigt.
- Wenn ein Befehl nicht sinnvoll komplett ausgefuehrt werden kann (z.B. lang laufender MCP-Server), musst du den realistisch maximal sinnvollen Test trotzdem durchfuehren und die Grenze dokumentieren.
- Wenn ein Befehl mehrere materiell unterschiedliche Ausgabe- oder Integrationsmodi hat, teste mindestens einen menschenorientierten und einen maschinenorientierten Pfad und dokumentiere ungetestete Modi explizit.
- Speichere relevante Rohoutputs, JSON-Artefakte und erzeugte Dateien unter `work_artifacts/drift_agent_test_<DATUM>/` und verweise im Bericht darauf.
- Fuer Fehlerpfade sollst du, wo sinnvoll, auch maschinenlesbare Fehler testen, z.B. mit `DRIFT_ERROR_FORMAT=json`.

## Pflicht-Coverage

Die aktuelle Inventur ueber `drift --help` ist verbindlich. Solange diese Befehle verfuegbar sind, muessen sie mindestens einmal in einem sinnvollen Workflow vorkommen:

- `scan`
- `analyze`
- `explain`
- `fix-plan`
- `diff`
- `validate`
- `check`
- `baseline save`
- `baseline diff`
- `config validate`
- `config show`
- `init`
- `copilot-context`
- `export-context`
- `mcp`
- `patterns`
- `timeline`
- `trend`
- `self`
- `badge`

Falls `drift --help` weitere Befehle zeigt, erweitere die Coverage automatisch und teste auch diese.

---

## Phase 0: Setup und CLI-Inventur

**Dieser Schritt ist verpflichtend und darf nicht übersprungen werden.**

Installiere die neueste Version von `drift-analyzer` von PyPI und verifiziere die Installation:

```bash
pip install --upgrade drift-analyzer
drift scan --help
```

Pruefe die installierte Version:

```bash
python -c "import drift; print(drift.__version__)"
```

Vergleiche mit der aktuellsten veroeffentlichten Version auf PyPI:

```bash
pip index versions drift-analyzer 2>/dev/null || pip install drift-analyzer== 2>&1 | grep -oP 'from versions: \K.*'
```

Inventarisiere anschliessend den realen CLI-Umfang:

```bash
drift --help
drift baseline --help
drift config --help
```

Erstelle danach sofort eine **Coverage-Matrix** aller gefundenen Befehle und Subcommands mit diesen Spalten:

| Kommando | Kategorie | Geplanter Praxisfall | Status | Evidence-Datei |
|----------|-----------|----------------------|--------|----------------|

### Bewerte:
- [ ] Die installierte Version entspricht der neuesten auf PyPI verfügbaren Version
- [ ] `drift scan --help` zeigt die erwarteten Parameter (u.a. `--max-findings`, `--response-detail`)
- [ ] `drift --help` wurde inventarisiert und die Coverage-Matrix ist vollstaendig angelegt
- [ ] `baseline`- und `config`-Subcommands wurden gesondert inventarisiert
- [ ] Falls die Version **nicht** die neueste ist: Dokumentiere die Abweichung und brich **nicht** ab, sondern teste mit der verfuegbaren Version und vermerke dies im Ergebnisbericht

Halte die installierte Version fest — sie wird im Ergebnisbericht unter `drift-Version` eingetragen.

---

## Phase 1: Agent Session Triage auf dem echten Repo

Nutze das aktuelle Repository so, wie ein Coding Agent es zu Beginn einer Session nutzen wuerde.

Fuehre mindestens aus:

```bash
drift scan --max-findings 15 --response-detail concise
drift scan --max-findings 15 --response-detail detailed
```

Wiederhole den Scan anschliessend in mindestens einem realistischen Scope, den du aus dem ersten Scan ableitest:

```bash
drift scan --target-path <ORDNER_MIT_HOHER_RELEVANZ> --max-findings 10 --response-detail concise
```

### Bewerte:
- [ ] Sind die `recommended_next_actions` klar genug, um deinen nächsten Schritt zu bestimmen?
- [ ] Ist `accept_change` eindeutig interpretierbar?
- [ ] Gibt es einen klaren Einstiegspunkt (z.B. `fix_first`, höchst-priorisierter Befund)?
- [ ] Bei >20 Findings: Wird ein Baseline-Workflow empfohlen?
- [ ] Unterscheiden sich `concise` und `detailed` sinnvoll aus Agentensicht?
- [ ] Laesst sich aus dem Scan ein konkreter Reparatur- oder Review-Workflow ableiten?

---

## Phase 2: Explain — Signalverständnis prüfen

Nimm das Signal mit dem hoechsten Score aus Phase 1 und fuehre aus:

```bash
drift explain <SIGNAL_ABBREVIATION>
```

Falls der Scan mehrere deutlich unterschiedliche Problemklassen zeigt, erklaere mindestens **zwei** Signale: das dominante Signal und ein zweites Signal mit abweichender Ursache.

### Bewerte:
- [ ] Erklärt die Antwort das Signal so, dass du als Agent darauf reagieren kannst?
- [ ] Ist klar, welche Code-Muster dieses Signal auslösen?
- [ ] Gibt es actionable Hinweise (nicht nur Theorie)?
- [ ] Ist klar, wie das Signal in einen echten Refactoring- oder Review-Schritt uebersetzt wird?

---

## Phase 3: Fix-Plan und reale Reparaturvorbereitung

### 3a: Ungescoped (gesamtes Repo)

```bash
drift fix-plan --max-tasks 5
```

### 3b: Gescoped auf einen Unterordner

Wähle den Ordner mit den meisten Findings aus Phase 1:

```bash
drift fix-plan --max-tasks 5 --target-path <ORDNER>
```

### 3c: Gescoped auf ein einzelnes Signal

```bash
drift fix-plan --signal <SIGNAL> --max-tasks 3
```

### 3d: Konkreter Task fuer echte Umsetzung

Waehle den aus Agentensicht am besten umsetzbaren Task aus den obigen Ergebnissen und versuche, **eine reale, kleine und risikoarme Verbesserung** im Repository vorzubereiten. Nutze dafuer, wenn sinnvoll, auch einen engeren Plan:

```bash
drift fix-plan --finding-id <FINDING_ID>
```

Wenn keine sichere echte Verbesserung moeglich ist, dokumentiere die Gruende und benenne den kleinsten realistischen naechsten Schritt, statt sofort auf eine kuenstliche Aenderung auszuweichen.

### Bewerte für jede Variante:
- [ ] Sind die Tasks konkret genug, um sie direkt umzusetzen?
- [ ] Enthalten die Tasks Datei + Zeilennummer?
- [ ] Gibt es `success_criteria` pro Task?
- [ ] Ist `automation_fitness` für jeden Task angegeben?
- [ ] Wird bei `--target-path` korrekt gefiltert (keine Tasks außerhalb)?
- [ ] Hilft `--finding-id` dabei, von Planung auf echte Umsetzung umzuschalten?
- [ ] Ist klar, welcher Task fuer einen autonomen Coding-Agenten zuerst sinnvoll ist?

---

## Phase 4: Reale Change-Review-Schleife

Wenn du in Phase 3 eine echte kleine Aenderung umgesetzt hast, pruefe den Arbeitsbaum so, wie ein Agent oder Reviewer ihn vor einem Commit pruefen wuerde.

Fuehre mindestens aus:

```bash
drift diff --uncommitted --response-detail detailed
```

Wenn du gezielt gestagte Aenderungen vorbereitet hast, teste zusaetzlich:

```bash
drift diff --staged-only --response-detail concise
```

Falls keine echte Aenderung moeglich war, erstelle eine minimale Testaenderung **nur als Fallback** und dokumentiere, warum der praxisnahe Pfad nicht moeglich war.

### Bewerte:
- [ ] Ist `accept_change` klar begründet?
- [ ] Werden `in_scope_accept` und `out_of_scope_noise` unterschieden?
- [ ] Wenn `accept_change=false` nur wegen out-of-scope Noise: Wird das explizit kommuniziert?
- [ ] Sind die `recommended_next_actions` handlungsrelevant?
- [ ] Gibt es eine Sackgasse, aus der du als Agent nicht herauskommst?
- [ ] Unterstuetzt der Diff-Output einen echten Pre-Commit- oder PR-Review-Workflow?

---

## Phase 5: Validate, Check und CI-Relevanz

### 5a: Ergebnis bestaetigen

```bash
drift validate
```

Wenn in Phase 3 oder 4 eine Baseline oder Datei-Artefakte entstanden sind, pruefe zusaetzlich einen praxisnahen Vergleich:

```bash
drift validate --baseline <BASELINE_DATEI>
```

### 5b: CI- und Gate-Workflow pruefen

Fuehre den Befehl so aus, wie er in CI oder pre-push genutzt werden koennte:

```bash
drift check --fail-on none --json --compact
drift check --fail-on high --output-format rich
```

Wenn eine Baseline vorliegt, teste auch deren Einfluss:

```bash
drift check --fail-on none --baseline <BASELINE_DATEI> --json --compact
```

### Bewerte:
- [ ] Bestätigt die Antwort den Fortschritt gegenüber Phase 1?
- [ ] Ist klar, ob die Änderungen die Drift-Score verbessert haben?
- [ ] Ist `check` fuer CI, pre-push oder PR-Gates direkt brauchbar?
- [ ] Sind Exit-Verhalten, Ausgabeformat und `fail-on` aus Agentensicht eindeutig?

---

## Phase 6: Vollanalyse, Baseline und Repository-Intelligence

Diese Phase prueft die Befehle, die Maintainer fuer tiefere Architekturarbeit nutzen.

### 6a: Vollanalyse

```bash
drift analyze --repo . --output-format rich
drift analyze --repo . --output-format json -o work_artifacts/drift_agent_test_<DATUM>/analyze.json
drift analyze --repo . --output-format sarif -o work_artifacts/drift_agent_test_<DATUM>/analyze.sarif
```

### 6b: Baseline fuer inkrementelle Einfuehrung

```bash
drift baseline save --repo . --output work_artifacts/drift_agent_test_<DATUM>/.drift-baseline.json
drift baseline diff --repo . --baseline-file work_artifacts/drift_agent_test_<DATUM>/.drift-baseline.json --format json
```

### 6c: Repository-Intelligence und Reporting

Teste anschliessend die uebrigen Analyse- und Reporting-Befehle in passenden realen Faellen:

```bash
drift patterns
drift timeline
drift trend
drift self --format json
drift badge --output work_artifacts/drift_agent_test_<DATUM>/badge.txt
```

### Bewerte:
- [ ] Ist `analyze` fuer einen Maintainer aussagekraeftig genug, um Prioritaeten abzuleiten?
- [ ] Ist `baseline save/diff` fuer inkrementelle Einfuehrung oder Noise-Reduktion wirklich brauchbar?
- [ ] Helfen `patterns`, `timeline` und `trend` bei echten Architekturentscheidungen oder liefern sie nur Zusatzoberflaeche?
- [ ] Ist `self` fuer Produkt-Dogfooding, Regressionen oder Demo-Zwecke nuetzlich?
- [ ] Erzeugt `badge` einen sinnvollen Output fuer README/CI-Artefakte?

---

## Phase 7: Setup-, Config- und AI-Integrations-Workflows

Diese Phase testet reale Einfuehrungs- und Agentenintegrationspfade.

### 7a: Sandbox vorbereiten

Lege unter `work_artifacts/drift_agent_test_<DATUM>/sandbox/` ein isoliertes Test-Repo oder Testverzeichnis an. Nutze diese Sandbox fuer schreibende Integrationsbefehle.

### 7b: Init und Config

Teste den Onboarding-Workflow in der Sandbox:

```bash
drift init --full --repo <SANDBOX_REPO>
drift config validate --repo <SANDBOX_REPO>
drift config show --repo <SANDBOX_REPO>
```

### 7c: Copilot- und Prompt-Kontext

Teste sowohl Vorschau als auch Dateiausgabe:

```bash
drift copilot-context --repo .
drift copilot-context --repo . --write -o work_artifacts/drift_agent_test_<DATUM>/copilot-instructions.md

drift export-context --repo . --format instructions --write -o work_artifacts/drift_agent_test_<DATUM>/negative-context.instructions.md
drift export-context --repo . --format prompt --write -o work_artifacts/drift_agent_test_<DATUM>/negative-context.prompt.md
drift export-context --repo . --format raw --write -o work_artifacts/drift_agent_test_<DATUM>/negative-context.raw.md
```

### 7d: MCP-Integration

Teste mindestens diese beiden Pfade:

```bash
drift mcp
drift mcp --serve
```

Wenn `drift mcp --serve` erfolgreich startet und blockiert, fuehre den Test mit Timeout oder als kurzzeitigem Hintergrundprozess aus und bewerte Startverhalten, Vorbedingungen und Bedienbarkeit. Wenn die Umgebung die optionalen Abhaengigkeiten nicht hat, bewerte die Fehlermeldung auf Agententauglichkeit.

### Bewerte:
- [ ] Ist `init` fuer ein neues Repo sofort brauchbar?
- [ ] Sind `config validate` und `config show` fuer Troubleshooting und Team-Onboarding ausreichend?
- [ ] Sind `copilot-context` und `export-context` fuer reale AI-Workflows verwendbar?
- [ ] Ist der MCP-Pfad fuer einen Agenten klar genug dokumentiert und testbar?

---

## Phase 8: Edge Cases und maschinenlesbare Fehler testen

### 8a: Ungueltiges Signal

```bash
drift fix-plan --signal INVALID_SIGNAL
```

- [ ] Gibt es eine hilfreiche Fehlermeldung mit gültigen Werten?

### 8b: Leerer Target-Path

```bash
drift fix-plan --target-path nonexistent/path
```

- [ ] Wird klar kommuniziert, dass keine Tasks gefunden wurden?

### 8c: Scan mit Signal-Filter

```bash
drift scan --signals PFS,AVS --max-findings 5
```

- [ ] Werden nur die angeforderten Signale angezeigt?

### 8d: Fehlende Baseline

```bash
drift baseline diff --repo <SANDBOX_REPO>
```

- [ ] Ist die Fehlermeldung klar und fuehrt sie zum naechsten sinnvollen Schritt?

### 8e: Did-you-mean fuer falsche Optionen

```bash
drift scan --max-fidings 5
```

- [ ] Gibt es einen brauchbaren Korrekturhinweis?

### 8f: Maschinenlesbarer Fehlerpfad

```bash
DRIFT_ERROR_FORMAT=json drift fix-plan --signal INVALID_SIGNAL
```

- [ ] Ist das Fehlerformat fuer Agenten stabil, vollstaendig und direkt automatisierbar?

---

## Phase 9: Ergebnisbericht erstellen

Erstelle einen strukturierten Bericht im folgenden Format:

```markdown
# Drift Agent-Workflow-Testergebnis

**Datum:** [DATUM]
**drift-Version:** [VERSION aus drift scan output]
**Repository:** [REPO-NAME]

## Zusammenfassung

| Phase | Befehl | Ergebnis | Agent-Tauglichkeit |
|-------|--------|----------|-------------------|
| 1     | scan   | ✅/⚠️/❌ | [kurze Bewertung] |
| 2     | explain | ✅/⚠️/❌ | [kurze Bewertung] |
| 3a    | fix-plan | ✅/⚠️/❌ | [kurze Bewertung] |
| 3b    | fix-plan --target-path | ✅/⚠️/❌ | [kurze Bewertung] |
| 3c    | fix-plan --signal | ✅/⚠️/❌ | [kurze Bewertung] |
| 3d    | fix-plan --finding-id | ✅/⚠️/❌ | [kurze Bewertung] |
| 4     | diff   | ✅/⚠️/❌ | [kurze Bewertung] |
| 5a    | validate | ✅/⚠️/❌ | [kurze Bewertung] |
| 5b    | check | ✅/⚠️/❌ | [kurze Bewertung] |
| 6a    | analyze | ✅/⚠️/❌ | [kurze Bewertung] |
| 6b    | baseline save/diff | ✅/⚠️/❌ | [kurze Bewertung] |
| 6c    | patterns/timeline/trend/self/badge | ✅/⚠️/❌ | [kurze Bewertung] |
| 7b    | init + config | ✅/⚠️/❌ | [kurze Bewertung] |
| 7c    | copilot-context + export-context | ✅/⚠️/❌ | [kurze Bewertung] |
| 7d    | mcp | ✅/⚠️/❌ | [kurze Bewertung] |
| 8a    | invalid signal | ✅/⚠️/❌ | [kurze Bewertung] |
| 8b    | empty result | ✅/⚠️/❌ | [kurze Bewertung] |
| 8c    | signal filter | ✅/⚠️/❌ | [kurze Bewertung] |
| 8d    | missing baseline | ✅/⚠️/❌ | [kurze Bewertung] |
| 8e    | did-you-mean | ✅/⚠️/❌ | [kurze Bewertung] |
| 8f    | machine-readable errors | ✅/⚠️/❌ | [kurze Bewertung] |

## Coverage-Matrix

| Kommando | Testfall | Status | Agent-Tauglichkeit | Evidence |
|----------|----------|--------|--------------------|----------|
| [jeder inventarisierte Befehl und Subcommand] | [...] | getestet / uebersprungen / blockiert | ausreichend / unzureichend / irrefuehrend | [Pfad oder n/a] |

## Praxis-Workflows

### 1. Session-Start eines Coding-Agents
[Welche Befehle waren hier wirklich hilfreich?]

### 2. Echte Reparatur- oder Refactoring-Vorbereitung
[Welche Befehle haben direkt bei der Umsetzung geholfen?]

### 3. PR-/CI-Gate
[Welche Befehle sind fuer Review, Pre-Commit oder CI brauchbar?]

### 4. Team-Onboarding / erstmalige Einfuehrung
[Wie brauchbar sind init, baseline und config?]

### 5. AI-Integration
[Wie brauchbar sind copilot-context, export-context und mcp?]

## Sackgassen (Agent konnte nicht weitermachen)

[Liste aller Stellen, wo der Workflow blockiert war]

## Unklare Antworten (Agent musste raten)

[Liste aller Stellen, wo die API-Antwort mehrdeutig war]

## Verbesserungsvorschläge (priorisiert)

1. [Höchste Priorität — blockiert Agent-Workflow]
2. [...]
3. [...]
```

Speichere den Bericht als `work_artifacts/drift_agent_test_[DATUM].md`.

---

## Phase 10: GitHub Issues für Drift erstellen

**Dieser Schritt ist der eigentliche Zweck des Tests.** Die im Bericht identifizierten Probleme werden als Issues im drift-Repo ([sauremilk/drift](https://github.com/sauremilk/drift)) angelegt, damit sie in zukünftige Releases einfließen können.

### Regeln für Issue-Erstellung

- Erstelle **nur Issues für Probleme mit ❌ oder ⚠️** aus der Zusammenfassungstabelle
- **Kein Issue** für ✅-Ergebnisse
- **Maximal ein Issue pro konkretem Problem** — keine Duplikate
- Prüfe vor der Erstellung, ob ein ähnliches Issue im Repo bereits existiert
- Verweise im Issue immer auf den konkreten Praxis-Workflow, in dem das Problem auftrat
- Nenne immer das konkrete Kommando und wenn moeglich die gespeicherte Evidence-Datei aus `work_artifacts/`

### Issue-Format

Für jedes Problem aus den Abschnitten "Sackgassen" und "Unklare Antworten" erstelle ein Issue mit:

**Titel:** `[agent-ux] <kurze Problembeschreibung in einem Satz>`

**Body-Template:**
```
## Beobachtetes Verhalten

[Was hat der Agent als Antwort bekommen?]

## Erwartetes Verhalten

[Was hätte der Agent brauchen, um weitermachen zu können?]

## Reproduktion

drift-Version: [VERSION]
Befehl: `drift <befehl> [parameter]`
Repo: [REPO-NAME]

## Auswirkung

- [ ] Sackgasse (Agent kann nicht weitermachen)
- [ ] Fehlinterpretation möglich (Agent muss raten)
- [ ] Informationsverlust (relevante Daten fehlen in Antwort)

## Quelle

Automatisch erstellt durch `prompts/drift-agent-workflow-test.prompt.md` am [DATUM].
```

**Labels:** `agent-ux`

### Prioritätsregel

Erstelle Issues in dieser Reihenfolge:
1. Sackgassen zuerst (blockieren den Workflow vollständig)
2. Unklare Antworten (erzeugen Fehler in Folgeschritten)
3. Fehlende Informationen (führen zu suboptimalen Entscheidungen)

### Abschluss

Gib am Ende eine Liste aller erstellten Issues aus:

```
Erstellte Issues:
- #[NR]: [Titel] — [URL]
- ...

Übersprungene Probleme (bereits als Issue vorhanden):
- [Titel] → #[NR]
```

## Erfolgskriterium

Der Workflow ist nur dann abgeschlossen, wenn:

- die Coverage-Matrix **alle aktuell verfuegbaren Befehle** aus `drift --help` inklusive relevanter Subcommands abdeckt
- mindestens vier reale Nutzungsszenarien getestet wurden: Session-Start, Reparatur/Refactoring, CI/Gate, Onboarding/Einfuehrung oder AI-Integration
- fuer schreibende Befehle echte Artefakte in `work_artifacts/` oder einer Sandbox erzeugt wurden
- die Unterschiede zwischen hilfreichen, unklaren und irrefuehrenden Antworten nachvollziehbar belegt sind
- alle Issue-wuerdigen Probleme als neue oder bereits vorhandene GitHub-Issues dokumentiert sind


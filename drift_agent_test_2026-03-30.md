# Drift Agent-Workflow-Testergebnis

**Datum:** 30. März 2026
**drift-Version:** 0.10.10
**Repository:** Real-Time Fortnite Coach

## Zusammenfassung

| Phase | Befehl | Ergebnis | Agent-Tauglichkeit |
|-------|--------|----------|-------------------|
| 1 | scan | ✅ | ausreichend: liefert Einstieg, `fix_first` und Baseline-Hinweis; aber Ties bei Top-Signalen und doppelte `fix_first`-Einträge zwingen den Agenten zu zusätzlicher Interpretation |
| 2 | explain | ✅ | ausreichend: `drift explain BAT` erklärt Trigger, typische Muster und konkrete Gegenmaßnahmen klar genug für einen Agenten |
| 3a | fix-plan | ✅ | ausreichend: ungescopter Plan ist konkret, mit Datei, Startzeile, Constraints, `success_criteria` und `automation_fit` |
| 3b | fix-plan --target-path | ⚠️ | teilweise ausreichend: Scope-Filter auf `backend/api/routers` greift korrekt, aber der Plan springt auf DCA-Tasks statt auf die im Scan sichtbaren PFS-Cluster |
| 3c | fix-plan --signal | ⚠️ | teilweise ausreichend: signal-spezifischer PFS-Plan ist umsetzbar, aber ohne Zeilennummern, mit vielen Dubletten in `related_files` und einem irreführenden `drift analyze`-Verweis in `success_criteria` |
| 4 | diff | ⚠️ | unzureichend im realen Agent-Workflow: auf einem dirty Worktree fehlt eine klare Trennung zwischen relevanten Änderungen und bestehendem Noise |
| 5 | validate | ❌ | irreführend: `drift validate` validiert hier nur Tool-/Repo-Fähigkeiten und nicht den Fortschritt gegenüber Phase 1 |
| 6a | error handling | ✅ | ausreichend: ungültiges Signal liefert strukturierte, recoverable Fehlermeldung inklusive gültiger Werte und Beispiel-Call |
| 6b | empty result | ⚠️ | unzureichend: nicht existierender `target-path` ergibt nur `task_count: 0`, aber keine explizite Pfad- oder Scope-Erklärung |
| 6c | signal filter | ❌ | unzureichend: der im Prompt erwartete Befehl `scan --signals PFS,AVS --max-findings 5` funktioniert in 0.10.10 nicht; praktikabler Workaround ist `scan --select PFS,AVS --max-findings 5` |

## Detailbewertung pro Phase

### Phase 0 - Setup

- `pip install --upgrade drift-analyzer` hat erfolgreich von 0.10.9 auf 0.10.10 aktualisiert.
- `python -c "import drift; print(drift.__version__)"` meldet 0.10.10.
- `pip index versions drift-analyzer` zeigt 0.10.10 als `LATEST` und `INSTALLED`.
- `drift scan --help` enthält `--max-findings` und `--response-detail`.
- Der Prompt erwartete zusätzlich `--signals`, aber im Help taucht stattdessen `--select` auf. Das ist eine relevante CLI-Vertragsabweichung.

**Agentisches Urteil:** teilweise ausreichend. Version und Kernparameter sind sauber prüfbar, aber der Signalfilter weicht von der erwarteten Schnittstelle ab.

### Phase 1 - Scan

- `drift scan --max-findings 15 --response-detail concise` liefert ein strukturiertes JSON mit `recommended_next_actions`, `fix_first`, `top_signals` und Baseline-Hinweis.
- Positiv: Der Hinweis auf `drift baseline save` kam automatisch bei vielen bestehenden Findings und ist für Agenten direkt handlungsrelevant.
- Negativ: `fix_first` enthält Dubletten für dieselben Dateien und priorisiert Ties bei mehreren 1.0-Signalen nicht sauber.

**Agentisches Urteil:** ausreichend.

### Phase 2 - Explain

- Gewähltes Signal: `BAT` als eines der höchstbewerteten Signale mit Score 1.0.
- `drift explain BAT` war klar strukturiert: Bedeutung, erkannte Muster, Beispiel, konkrete Reparaturansätze.
- Besonders hilfreich: Die Erklärung benennt genau die Marker, die der Agent im Code suchen müsste, etwa `# type: ignore`, `typing.Any`, `cast()` und `TODO/FIXME/HACK`.

**Agentisches Urteil:** ausreichend.

### Phase 3a - Fix-Plan ungescoped

- `drift fix-plan --max-tasks 5` liefert fünf Tasks mit Datei, `start_line`, Priorität, `automation_fit`, `success_criteria` und Constraints.
- Die Aufgaben sind direkt umsetzbar und gut auf lokale, minimale Änderungen zugeschnitten.

**Agentisches Urteil:** ausreichend.

### Phase 3b - Fix-Plan mit Target-Path

- `drift fix-plan --max-tasks 5 --target-path backend/api/routers` liefert ausschließlich Tasks innerhalb des Zielordners.
- Die Filterung ist damit korrekt.
- Inhaltlich springt die Antwort aber auf DCA, obwohl der Scan in diesem Bereich vor allem PFS-Fragmente sichtbar machte. Das ist nicht falsch, aber für einen Agenten überraschend und erfordert Nachdenken statt direkter Ausführung.

**Agentisches Urteil:** ausreichend bis unzureichend, je nach Erwartung an Vorhersagbarkeit.

### Phase 3c - Fix-Plan mit Signal

- `drift fix-plan --signal PFS --max-tasks 3` liefert passende PFS-Aufgaben.
- Positiv: `automation_fit`, `success_criteria` und erwartete Wirkung sind vorhanden.
- Negativ:
  - keine Zeilennummern für die eigentlichen Reparaturstellen
  - stark duplizierte `related_files`
  - `success_criteria` verweist auf `drift analyze`, obwohl in diesem Workflow sonst `scan`, `fix-plan`, `diff`, `validate` benutzt werden

**Agentisches Urteil:** teilweise ausreichend.

### Phase 4 - Diff

- `drift diff` lief technisch erfolgreich.
- In einem realistischen Agenten-Workflow mit bereits vielen vorhandenen Änderungen ist die Antwort aber nur begrenzt brauchbar:
  - `accept_change: false`
  - `in_scope_accept: false`
  - `out_of_scope_new_count: 0`
  - gleichzeitig `new_finding_count: 127`
  - und `drift_detected: false`
- Diese Kombination ist semantisch schwer zu interpretieren. Der Agent sieht viele neue Findings, aber keine explizite Noise-Trennung und keine automatische Empfehlung, jetzt einen Baseline- oder Scope-Workflow nachzuschieben.

**Agentisches Urteil:** unzureichend.

### Phase 5 - Validate

- `drift validate` meldet nur technische Gültigkeit des Setups: `capabilities`, `config_source`, `git_available`, `valid`.
- Es gibt keinen Vergleich zu Phase 1, keinen Score-Fortschritt und keine Aussage, ob Änderungen etwas verbessert haben.

**Agentisches Urteil:** irreführend für diesen Workflow.

### Phase 6a - Ungültiges Signal

- `drift fix-plan --signal INVALID_SIGNAL` liefert eine saubere strukturierte Fehlermeldung.
- Besonders hilfreich:
  - `error_code`
  - `invalid_fields`
  - `recoverable: true`
  - `valid_values`
  - `example_call`

**Agentisches Urteil:** ausreichend.

### Phase 6b - Leerer Target-Path

- `drift fix-plan --target-path nonexistent/path` liefert `task_count: 0` und `total_available: 0`.
- Es fehlt aber eine explizite Aussage, ob der Pfad nicht existiert, leer ist oder nur keine Findings enthält.

**Agentisches Urteil:** unzureichend.

### Phase 6c - Scan mit Signal-Filter

- Der im Prompt erwartete Aufruf `drift scan --signals PFS,AVS --max-findings 5` schlägt fehl mit: `No such option: --signals`.
- Der Help-Text von 0.10.10 zeigt stattdessen `--select`.
- Workaround getestet: `drift scan --select PFS,AVS --max-findings 5` funktioniert und liefert nur PFS-/AVS-relevante Ergebnisse.

**Agentisches Urteil:** unzureichend für den dokumentierten Workflow, aber mit klarem Workaround.

## Welche Befehle funktioniert haben

- `pip install --upgrade drift-analyzer`
- `drift scan --help`
- `python -c "import drift; print(drift.__version__)"`
- `python -m pip index versions drift-analyzer`
- `drift scan --max-findings 15 --response-detail concise`
- `drift explain BAT`
- `drift fix-plan --max-tasks 5`
- `drift fix-plan --max-tasks 5 --target-path backend/api/routers`
- `drift fix-plan --signal PFS --max-tasks 3`
- `drift diff`
- `drift validate`
- `drift fix-plan --signal INVALID_SIGNAL`
- `drift fix-plan --target-path nonexistent/path`
- `drift scan --select PFS,AVS --max-findings 5`

## Welche Befehle unklare oder unbrauchbare Ergebnisse lieferten

- `drift scan --max-findings 15 --response-detail concise`
  Grund: Top-Signal-Ties werden nicht aufgelöst, `fix_first` enthält Dubletten.
- `drift fix-plan --max-tasks 5 --target-path backend/api/routers`
  Grund: Filter korrekt, aber fachlich unerwarteter Fokuswechsel auf DCA.
- `drift fix-plan --signal PFS --max-tasks 3`
  Grund: keine Zeilennummern, viele Datei-Dubletten, uneinheitliche Command-Referenz.
- `drift diff`
  Grund: in dirty Worktrees fehlt explizite Noise-Separation.
- `drift validate`
  Grund: bestätigt nicht den Fortschritt des Workflows, sondern nur das Setup.
- `drift fix-plan --target-path nonexistent/path`
  Grund: leeres Resultat ohne erklärende Ursache.

## Sackgassen (Agent konnte nicht weitermachen)

- `drift scan --signals PFS,AVS --max-findings 5` war eine echte Sackgasse, weil die Option in 0.10.10 nicht existiert.
- `drift validate` war für diesen Workflow eine Sackgasse, weil kein Fortschritt gegenüber Phase 1 ausgewiesen wird.
- `drift diff` auf einem bereits stark veränderten Worktree lässt den Agenten ohne klare in-scope/out-of-scope Orientierung zurück.

## Unklare Antworten (Agent musste raten)

- In Phase 1 gab es mehrere höchstbewertete Signale mit Score 1.0, aber keine Empfehlung, welches zuerst erklärt werden soll.
- `fix_first` zeigte doppelte AVS-Einträge für dieselben Dateien.
- Der Target-Path-Plan war formal korrekt, aber semantisch nicht an den sichtbaren PFS-Befunden aus Phase 1 ausgerichtet.
- Der PFS-Plan verlangte Cross-Module-Konsolidierung, nannte aber keine präzisen Startzeilen.
- `drift diff` kombinierte `new_finding_count > 0` mit `drift_detected: false` und ohne Noise-Abgrenzung.

## Verbesserungsvorschläge (priorisiert)

1. CLI-Vertrag vereinheitlichen: `scan --signals` entweder unterstützen oder bei Nutzung automatisch auf `--select` umleiten und das im Fehlertext aktiv vorschlagen.
2. `drift validate` auf Workflow-Fortschritt ausrichten: Score vorher/nachher, aufgelöste Findings, regressierte Signale und Vergleich zu Phase 1 oder Baseline ausgeben.
3. `drift diff` in dirty Worktrees robuster machen: vorhandenes Noise explizit markieren, Baseline-Workflow automatisch empfehlen und `out_of_scope_noise` klar von in-scope Änderungen trennen.
4. `fix_first` und signal-spezifische Pläne entdoppeln: keine wiederholten Einträge, weniger Dubletten in `related_files`, konsistente Referenz auf echte CLI-Commands, Zeilennummern wo möglich.
5. Leere oder ungültige Scopes explizit erklären: `path not found`, `path contains no analyzable files` oder `path has no findings` statt eines still leeren Task-Sets.
6. TypeScript-/TSX-Support deutlicher adressieren: bei 135 übersprungenen Dateien sollte der Scan stärker markieren, dass die Analyse für das Dashboard unvollständig ist.

---
id: ADR-081
status: proposed
date: 2026-04-21
supersedes:
---

# ADR-081: Session-Queue-Persistenz via Append-Log

## Kontext

Fix-Plans und Task-Fortschritte liegen ausschließlich im `SessionManager` im RAM (ADR-022). Bei MCP-Server-Neustart, TTL-Ablauf (30 min) oder Agent-Crash geht der Queue-State verloren. Jede neue Agent-Session muss `drift_fix_plan` erneut aufrufen und begrifft die bisher erledigten Tasks nicht. Das führt zu **Ad-hoc-Fixes ohne Cross-Session-Kontinuität**: wiederholte Mikro-Patches statt kohärenter Batch-Arbeit, weil die priorisierte Reihenfolge bei jedem Restart verloren geht.

`SessionManager.save_to_disk()` / `load_from_disk()` existieren als vollständiger Snapshot, werden aber nur manuell aufgerufen und halten transienten Laufzeit-State (Leases, Metriken, Trace) fest — was bei Restart falsche Informationen reaktiviert.

## Entscheidung

**Einführen eines append-only Event-Logs `<repo>/.drift-cache/queue.jsonl`**, das ausschließlich Queue-Mutationen persistiert:

- `plan_created` → vollständige Task-Liste (Snapshot bei jedem `drift_fix_plan`)
- `task_claimed` → `{task_id, agent_id}` (transient, wird beim Replay ignoriert)
- `task_released` → `{task_id, reclaim_count}` (transient, ignoriert)
- `task_completed` → `{task_id}` (terminal, wirkt durch Replay fort)
- `task_failed` → `{task_id}` (terminal, wirkt durch Replay fort)

`drift_session_start` replayt den Log standardmäßig und rekonstruiert `selected_tasks`, `completed_task_ids`, `failed_task_ids` aus dem jüngsten `plan_created` + allen darauf folgenden terminalen Events. Ein neuer Parameter `fresh_start: bool = False` erlaubt es Agenten/Tests, diesen Replay zu überspringen.

### Replan-Semantik (Q4 Nachschärfung)

Die Reducer-Regel ist absichtlich *latest-plan-wins*:

1. Der Replay scannt den Log zweimal — zuerst, um das jüngste `plan_created`-Event zu bestimmen, dann, um darauf folgende terminale Events anzuwenden.
2. **Terminale Events, die vor dem gewinnenden `plan_created` liegen, werden verworfen.** `task_id`-Werte sind repo-lokal, aber nicht zwischen Plänen stabil: ein neuer `drift_fix_plan`-Lauf kann andere Finding-Cluster ausweisen, die die gleiche `task_id` bekommen, ohne dass sie dieselbe Arbeit beschreiben. Einen "Merge" zwischen alten Completions und einem neuen Plan durchzuführen wäre deshalb keine Sicherheits-, sondern eine Falschinformationsquelle.
3. Das Signal gegen externe Reviewer ist additiv: die `drift_session_start`-Response enthält `resumed_older_plans_discarded: int` — die Anzahl `plan_created`-Events, die vor dem gewinnenden lagen. Ein Wert > 0 ist erwartet, kein Fehler; er belegt nur, dass der Agent einen Replan durchgeführt hat und die alte Priorisierung nicht mehr relevant ist.
4. Alte `plan_created`-Events bleiben im Log erhalten, bis Rotation greift. Sie sind damit rekonstruierbar, falls ein Audit die frühere Priorisierung nachvollziehen möchte; sie beeinflussen aber nicht den ausgeführten Work-State.

### Concurrent-Writer-Advisory (Q3 Nachschärfung)

ADR-081 bleibt bei der **Single-Writer-pro-Repo**-Zusage und definiert diese nun ausdrücklich als *kooperativ, nicht erzwungen*. Die Implementierung ergänzt:

- `<repo>/.drift-cache/queue.lock`, geschrieben bei `drift_session_start` mit `{pid, session_id, started_at}`, entfernt bei `drift_session_end`.
- Bei Session-Start liest der Router den existierenden Holder. Wenn die PID lebt (POSIX: `os.kill(pid, 0)`, Windows: `OpenProcess`/`GetExitCodeProcess` via `ctypes`) und das Lockfile jünger als 24 h ist, wird der vorherige Writer in der Response als `concurrent_writer`-Objekt plus `concurrent_sessions_detected=true` gemeldet und `agent_instruction` erweitert.
- **Keine harte Sperre**: der startende Prozess übernimmt das Lockfile immer ("last session wins"), damit eine tote Session (SIGKILL, OOM) das Repo nicht blockiert.
- Eine Hard-Lock-Variante (zweite Session schlägt fehl) wäre eigenständiges Risiko-Delta — eigene ADR mit Recovery-Pfad für verwaiste Locks, keine Unterschrift hier.

### Resume-UX-Routing (Q5 Nachschärfung)

Bei erfolgreichem Replay mit offenen Aufgaben setzt `drift_session_start` `next_tool_call` auf `drift_fix_apply` mit dem ersten ausstehenden `task_id` (Sortierung: `priority_score` DESC, sonst FIFO). Die Q2-Override (Plan stale) dominiert und zeigt weiterhin auf `drift_fix_plan`. Ziel: Agent arbeitet die persistierte Queue ab, statt erneut zu scannen.

**Explizit nicht Teil der Entscheidung**:

- Leases und Metriken werden beim Replay nicht wiederhergestellt (abgelaufene Leases würden neue Claims blockieren, Metriken sind per-Session).
- Keine Multi-Prozess-Koordination: ein Writer pro Repo-Arbeitskopie; OS-Lock nur als Best-Effort-Absicherung gegen versehentliche parallele Schreiber.
- Der bestehende Snapshot-Pfad `save_to_disk`/`load_from_disk` bleibt unverändert und dient Debug/Export.

## Begründung

Append-Log statt Snapshot wurde gewählt, weil:

1. **Atomische Append-Semantik** auf den üblichen Dateisystemen verhindert Lost-Update-Konflikte bei parallelen Task-Mutationen innerhalb eines Prozesses.
2. **Audit-Trail**: Events sind chronologisch und nicht destruktiv; eine Rotation kompaktiert (verwirft nur noch transiente Events), verfälscht aber keine terminalen Entscheidungen.
3. **Forward-Compatibility**: jedes Event trägt ein `v`-Feld und unbekannte `type`-Werte werden beim Replay übersprungen, sodass zukünftige Event-Typen (z. B. `task_dismissed`, `plan_invalidated`) rückwärtskompatibel hinzugefügt werden können.
4. **Robustheit**: korrupte Einzelzeilen werden beim Replay geloggt und übersprungen, nicht als Fatal-Error behandelt.

Alternative "Full-Snapshot pro Mutation" wurde verworfen, weil sie bei großen Task-Listen teuer ist, Race-Conditions bei parallelen Writern verschärft und keinen Audit-Trail liefert.

Framing als `fix:` (Adoption-Blocker für MCP-Fix-Loop) statt `feat:` wurde begründet durch Policy §8 Einführbarkeit: Ad-hoc-Fix-Chaos zwischen Sessions verhindert, dass agentische Nutzung empirisch nachgewiesen werden kann — ein direkter Blocker für die Distribution-Phase.

## Konsequenzen

**Positive**:

- Cross-Session-Queue-Kontinuität: Agent kann nach Editor-Neustart weiterarbeiten, ohne Fortschritt zu verlieren.
- Deterministisches Replay: identische Event-Reihenfolge → identischer rekonstruierter State.
- Kein neuer MCP-Tool-Name; nur ein neuer optionaler Parameter `fresh_start` auf `drift_session_start`.

**Negative / Trade-offs**:

- Ein weiterer Pfad, den Tests gegen Seiteneffekte isolieren müssen (`tmp_path`).
- `.drift-cache/queue.jsonl` kann in langlebigen Repos wachsen; Rotation bei 10 MB mindert, entfernt das Problem aber nicht vollständig.
- Best-Effort-Lock schützt nicht gegen bösartige Manipulation der Logdatei (Policy §18 STRIDE: Tampering — siehe audit_results-Aktualisierung).
- Replay rekonstruiert keinen lease/metric-State; wiederaufnahmepunkt ist bewusst "Plan + Abschlüsse", nicht "exakter Laufzeitzustand".

**Auswirkungen auf bestehende ADRs**:

- ADR-022 (Sessions): erweitert um persistierenden Queue-State auf Plan/Task-Ebene.
- ADR-025 (Task-Queue-Leasing, proposed): bleibt orthogonal — Leases bleiben transient.

## Validierung

- Unit-Tests in `tests/test_session_queue_log.py` belegen: Roundtrip, korrupte-Zeilen-Toleranz, Thread-Safety, Rotation-Kompaktierung, UTF-8-Korrektheit auf Windows.
- Integration-Tests in `tests/test_session.py::TestRestartReplay` belegen: Replay nach simuliertem Neustart, Opt-Out via `fresh_start=true`, Write-Hooks in `claim_task`/`complete_task`/`release_task`.
- Nachschärfung-Tests: `tests/test_session.py::TestResumedPlanStaleness` (Q2 Plan-Alter), `TestConcurrentWriterAdvisory` (Q3 Lock-Detection), `TestResumedNextToolCall` (Q5 fix_apply-Routing, Q4 Replan-Counter), `tests/test_session_writer_lock.py` (Advisory-Lock-Primitive).
- Evidenz: `benchmark_results/v2.27.0_feature_evidence.json` dokumentiert Roundtrip-Verhalten und Replay-Korrektheit.
- Policy §18: FMEA-, STRIDE- und Risk-Register-Einträge zu Queue-Log-Korruption, Tampering und Replay-Inkonsistenz.
- Lernzyklus-Ergebnis nach Distribution-Phase: **zurückgestellt** — bestätigt oder widerlegt anhand empirischer Nutzungsdaten agentischer Sessions.

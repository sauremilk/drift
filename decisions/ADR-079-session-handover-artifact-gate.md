---
id: ADR-079
status: proposed
date: 2026-04-21
supersedes:
---

# ADR-079: Session-Handover-Artefakt-Gate in drift_session_end

## Kontext

`drift_session_end` beendet heute eine MCP-Session mit einer flüchtigen JSON-Summary
(Dauer, Tool-Calls, Score-Delta, offene Tasks). Der Output bleibt im Agent-Kontext
und verschwindet mit dem Sessionende. Ein Folge-Agent hat keinen deterministischen
Einstiegspunkt: Offene Enden, Begründung verworfener Alternativen und
Audit-Referenzen gehen verloren, auch wenn die Session Signal-, Scoring- oder
Architekturflächen berührt hat.

Gleichzeitig bestehen im Repo bereits drei etablierte Handover-Artefakttypen:

- `benchmark_results/v<Version>_<slug>_feature_evidence.json` (siehe
  [drift-evidence-artifact-authoring](../.github/skills/drift-evidence-artifact-authoring/SKILL.md))
- ADR-Drafts unter `decisions/ADR-<NNN>-<slug>.md` (siehe
  [drift-adr-workflow](../.github/skills/drift-adr-workflow/SKILL.md))
- `audit_results/*.md` Pflichtupdates nach POLICY §18

Diese Artefakte werden heute nur durch Commit-Push-Gates und menschliche Disziplin
verlangt, nicht durch den MCP-Tool-Pfad selbst. Agenten umgehen die Pflicht gern
mit Placeholder-Prosa (`TODO`, `<N>`, leere Alternativ-Listen), weshalb ein rein
existenzbasierter Check Security-Theater wäre.

## Entscheidung

`drift_session_end` wird zu einem **Hard-Gate** umgebaut, das Session-Destroy nur
zulässt, wenn alle aus dem Session-Zustand abgeleiteten Pflichtartefakte real auf
Disk liegen und drei Validierungsschichten bestehen. Eine optionale vierte Schicht
(LLM-Review) kann per Environment-Flag aktiviert werden.

**Nicht getan wird:**

- Keine Änderung an `drift_session_start`, `drift_session_status`, `drift_session_update`.
- Keine Änderung an der stateless `drift.api`-Schicht.
- Keine Auto-Generierung von Evidence-Files oder ADRs durch den Server — der
  Agent schreibt vollständig selbst, der Server validiert nur.
- Keine CLI-Commands in dieser Iteration.
- Kein Auto-Write in `audit_results/` aus dem MCP-Pfad (zu invasiv).

### Detection (aus Session-Trace + Git-Diff)

`session_handover.classify_session()` leitet deterministisch eine `ChangeClass` ab:

| Touched-Pfade                                                              | Klasse         | Pflichtartefakte                                            |
|----------------------------------------------------------------------------|----------------|-------------------------------------------------------------|
| `src/drift/signals/**`, `src/drift/scoring/**`                             | `signal`       | evidence + ADR + session_*.md, `audit_artifacts_updated` ≥1 |
| `src/drift/ingestion/**`, `output/**`, `api/**`, `mcp_*.py`, `session*.py` | `architecture` | evidence + ADR + session_*.md                               |
| sonstige `src/drift/**`                                                    | `fix`          | session_*.md (evidence nur wenn feat: geplant)              |
| nur `docs/**`, `docs-site/**`, `.github/prompts|skills/**`                 | `docs`         | session_*.md                                                |
| nur Config, lockfile, Fixture-Rename                                       | `chore`        | session_*.md (Kompaktformat zulässig)                       |

Touched-Files werden primär aus `git diff --name-only <git_head_at_plan>..HEAD`
plus uncommitted-Changes ermittelt. Trace-Metadaten (`touched_files` aus
`record_trace`) sind sekundärer Fallback, falls kein Git-Head aus Session-Start
vorhanden ist.

### Validierungsschichten

- **L1 Existenz.** Jeder Required Path existiert und überschreitet Mindestgröße
  (200 Bytes für Markdown, 64 Bytes für JSON).
- **L2 Shape.** Pflichtfelder/Pflichtsektionen gemäß Contract-Partial
  [session-handover-contract.md](../.github/prompts/_partials/session-handover-contract.md).
  Frontmatter-Felder `session_id`, `duration_seconds`, `tasks_completed`,
  `findings_delta` werden gegen Session-State verifiziert (verhindert Copy-Paste
  aus Fremdsessions).
- **L3 Placeholder-Denylist.** `TODO`, `FIXME`, `XXX`, `tbd`, `lorem`, `ipsum`,
  `<N>`, `???`, `foo/bar/baz`, leere Bullet-Items, nur-Whitespace-Sektionen,
  ADR-Kontext unter 120 Zeichen. Regeln deterministisch in
  `src/drift/session_handover.py`.
- **L4 LLM-Review (optional).** Nur wenn `DRIFT_SESSION_END_LLM_REVIEW=1` gesetzt.
  Hook ruft konfigurierten Review-Agent, Ergebnis landet als `semantic_ok` in der
  Response. Fehlt das Flag → Feld nicht in Response.

### Fehler-Response und Retry

Blockiert ein Gate, antwortet `drift_session_end` mit `status=blocked`, Code
`DRIFT-6100`, strukturierter Fehlerliste (`missing_artifacts`, `shape_errors`,
`placeholder_flags`) und erweitert die Session-TTL um ein bounded Grace-Window
(`max_handover_retries=5`). Session wird nicht zerstört. Nach 5 blockierten
Versuchen oder bei explizitem `force=true` mit `bypass_reason` (mind. 40 Zeichen,
nicht auf Placeholder-Denylist) wird die Session beendet, der Bypass als
prominenter Warn-Log und Telemetrie-Event (`session_end.bypass`) festgehalten.

## Begründung

- **Handlungsfähigkeit:** Folge-Agents bekommen einen deterministischen Einstieg
  (versionierte Evidence + ADR + Session-Markdown), nicht nur flüchtige Prosa im
  Chat-Kontext.
- **Glaubwürdigkeit:** Dreistufige Validierung verhindert, dass Placeholder-MD
  als „Artefakt" durchrutscht. Ohne L2/L3 wäre das Gate Security-Theater.
- **Einführbarkeit:** Reine `docs`-/`chore`-Sessions werden mit einer einzigen
  kompakten Datei abgedeckt. Klassifikation ist aus Trace ableitbar, keine
  manuelle Deklaration nötig.
- **Minimale Umgehungsfläche:** `force=true` braucht eine auditierbare Begründung
  und wird telemetriert. Agent kann nicht „schnell closen".

### Alternativen

- **Alternative A: Nur Warnungen, Destroy immer zulassen.** Verworfen. Das
  bestehende Commit-Push-Gate kommt oft zu spät — der Session-State ist dann
  bereits weg und kann nicht mehr zur Klassifikation der Change-Class genutzt
  werden.
- **Alternative B: Agent deklariert `change_class` explizit.** Verworfen. Öffnet
  Downgrade-Pfad („docs-only, kein ADR nötig"), den der Server nicht gegenprüfen
  kann, wenn Trace nicht die autoritative Quelle bleibt.
- **Alternative C: Server generiert Artefakte auto-vorbefüllt.** Verworfen.
  Vorbefüllte ADRs mit leerem Kontext sind genau die Placeholder-Falle, die L3
  verhindern soll. Zusätzlich wäre Code-Write in `decisions/` und `audit_results/`
  aus dem MCP-Pfad zu invasiv.

## Konsequenzen

- Neues Modul `src/drift/session_handover.py` (~350 Zeilen: Klassifikation,
  Anforderungsableitung, L1–L4-Validatoren).
- `src/drift/mcp_router_session.py::run_session_end` wächst um Gate-Aufruf und
  `force`/`bypass_reason`-Parameter.
- `src/drift/mcp_server.py::drift_session_end` erhält zwei neue optionale
  Parameter (`force: bool`, `bypass_reason: str`); Abwärtskompatibilität bleibt
  erhalten (Default blockiert nur, wenn Session signalrelevant war).
- Neuer Fehlercode-Range `DRIFT-6100`–`DRIFT-6199` für Handover-Gate.
- Docstring-Gate greift für alle public functions im neuen Modul.
- FMEA und Risk-Register werden um den Eintrag
  „Handover-Gate-Umgehung via `force=true`" erweitert.

## Validierung

```bash
pytest tests/test_session_handover.py -v
pytest tests/test_mcp_hardening.py -v
pytest tests/test_situational_hints.py -v
pytest tests/ --ignore=tests/test_smoke_real_repos.py -m "not slow" -q -n auto
ruff check src/drift/session_handover.py src/drift/mcp_router_session.py
python -m mypy src/drift/session_handover.py src/drift/mcp_router_session.py
```

Erwartetes Lernzyklus-Ergebnis: `bestätigt`, wenn nach Rollout die Rate an
MCP-Sessions ohne Handover-Artefakt auf < 5 % fällt und keine zusätzlichen
`force=true`-Bypässe mit leerer `bypass_reason` in der Telemetrie auftauchen.

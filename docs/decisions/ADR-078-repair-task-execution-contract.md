---
id: ADR-078
status: proposed
date: 2026-04-20
supersedes:
---

# ADR-078: Repair-Task-Execution-Contract — Maschinenverifizierbarer Vertrag für autonome Agent-Fixes

## Kontext

Drift hat eine vollständige Erkennungs- und Planungsschicht: Signale, `fix_plan`, `AgentTask`,
`fix_intent` (ADR-063), `PatchIntent` (ADR-074) und `fix_apply` (ADR-076). Was fehlt, ist eine
**geschlossene Ausführungsschleife** — ein Vertrag, den ein LLM-Agent deterministisch abarbeiten
kann, ohne Mensch im Loop, und den drift danach automatisch verifizieren kann.

### Konkrete Lücken im bestehenden Stack

| Bestandteil | Lücke |
|---|---|
| `fix_intent.forbidden_changes` (ADR-063) | Advisory-only — kein maschinenverifizierbarer Erfolgsnachweis |
| `PatchIntent.acceptance_criteria: list[str]` (ADR-074) | Textstrings — nicht von drift auswertbar |
| `fix_apply` (ADR-076) | Kein automatisches Post-Fix-Verifikations-Routing |
| `repair_maturity: VERIFIED/EXPERIMENTAL` auf `AgentTask` | Ungenutzt für gestufte Verifikationserwartung |
| `drift_nudge(task_signal=..., task_edit_kind=...)` | Outcome-Recording-Parameter vorhanden, aber nicht automatisch befüllt |

### Symptom

Ein Agent, der heute einen `AgentTask` aus `fix_plan` erhält, muss:
1. Die `action`-Beschreibung (natürliche Sprache) interpretieren
2. Selbst entscheiden, wann er fertig ist
3. Manuell `drift_nudge` aufrufen und das Ergebnis interpretieren

Vollautonomie erfordert stattdessen, dass das Task-Objekt selbst sagt:
- **Was** exakt zu tun ist (das liefert `fix_intent` bereits)
- **Wie** verifiziert wird (fehlt — `acceptance_criteria: list[str]` ist nicht maschinenlesbar)
- **Welche Verifikation** gilt als Erfolg (fehlt — `repair_maturity` wird nicht ausgewertet)
- **Welches Tool** nach dem Fix automatisch aufzurufen ist (fehlt — kein Routing-Signal)

### Verweis auf externe Evidenz

METR-Analyse (2026-03-10): ~50 % der SWE-bench-passing PRs würden nicht in mainline gemergt —
weil Agenten auf "Tests grün" optimieren, nicht auf "Change ist korrekt". Drift-interne
Benchmark-Evidenz in `benchmark_results/v2.14.0_patch_engine_feature_evidence.json` zeigt
messbaren Wiederkehr-Effekt bei Fixes ohne root-cause-Adressierung (vgl. ADR-075).

---

## Entscheidungsfrage (offen)

Wie wird der maschinenlesbare Execution-Contract eingeführt?

### Option A — Neues first-class Modell `RepairTask`

Eine neue Klasse `RepairTask` (Pydantic, in `src/drift/models/_repair.py`) bildet den
vollständigen Execution-Contract ab — als eigenständige Abstraktionsschicht **über**
`AgentTask` und **vor** `PatchIntent`:

```
Finding → AgentTask (Planungsschicht) → RepairTask (Execution-Contract) → PatchIntent (Transaktionsschicht)
```

`RepairTask` enthält:
- Alle felder aus `AgentTask` via Bridge-Konstruktor
- `verification_spec: VerificationSpec` (neu, maschinenverifizierbar)
- `execution_instructions: list[ExecutionStep]` (geordnete, atomare Schritte)
- `auto_verification_tool: Literal["drift_nudge", "drift_shadow_verify"]` (Routing-Signal)

**Vorteile:** Saubere Separation of Concerns; `AgentTask` bleibt stabil; neues Modell kann
unabhängig versioniert werden.

**Nachteile:** Dritte Abstraktionsschicht zwischen Finding und Patch — erhöhte kognitive Last für
Agenten, die bereits `AgentTask` + `PatchIntent` kennen; mehr Boilerplate, mehr Schema-Fläche.

### Option B — Stack-Extension (Empfehlung des Agenten)

Keine neue Klasse. Stattdessen zwei minimale Erweiterungen:

1. `PatchIntent.acceptance_criteria: list[str]` → `acceptance_criteria: list[VerificationSpec]`
   (Typ-Upgrade, backward-compat über `VerificationSpec` mit `str`-Fallback-Feld)

2. `fix_apply` und `patch_commit`-Router lösen automatisch das korrekte Verifikations-Tool aus,
   gesteuert durch `VerificationSpec.verification_tool` und `edit_kind`-Routing.

```
Finding → AgentTask → to_patch_intent() → PatchIntent[VerificationSpec] → patch_commit → auto-verify
```

**Vorteile:** Weniger Oberfläche; `AgentTask.to_patch_intent()` ist bereits die Bridge;
Agenten lernen keine neue Klasse; backward-compat einfacher handhabbar.

**Nachteile:** `PatchIntent` wird semantisch breiter; Execution-Logik liegt in zwei Layern.

### Empfehlung

**Option B.** `AgentTask.to_patch_intent()` ist bereits die etablierte Bridge (ADR-074). Ein
drittes Modell würde Agenten, die den Stack kennen, mehr verwirren als ein Typ-Upgrade auf
einem bekannten Feld. Die entscheidende fehlende Abstraktion ist `VerificationSpec` — diese
lässt sich orthogonal zu der Modell-Entscheidung einführen.

---

## Entscheidung (vorzufüllen, wenn Status von `proposed` auf `accepted` wechselt)

_[ ] Option A: Neues `RepairTask`-Modell_
_[ ] Option B: Stack-Extension via `VerificationSpec`-Typ-Upgrade_

---

## Kernbaustein: `VerificationSpec`

Unabhängig von der Modell-Entscheidung ist `VerificationSpec` der zentrale neue Baustein.
Er macht `acceptance_criteria` maschinenauswertbar.

### Schema

```python
class VerificationSpec(BaseModel):
    """Maschinenverifizierbares Akzeptanzkriterium für einen Repair-Task."""

    resolved_signal: str
    """Signal-Typ (z. B. 'explainability_deficit'), der nach dem Fix auf 0 sinken muss
    (bei direction_required='resolved') oder sich verbessern muss (direction_required='improving')."""

    resolved_symbol: str | None = None
    """Optionaler FQN oder Name des primären Symbols — schränkt die Verifikation
    auf einen spezifischen Scope ein (verhindert false-positive-Resolved durch andere Fixes)."""

    direction_required: Literal["resolved", "improving"]
    """Abgeleitet aus repair_maturity des zugehörigen AgentTask:
    - VERIFIED   → 'resolved'   (signal_count muss sinken, safe_to_commit=true)
    - EXPERIMENTAL → 'improving' (direction='improving', safe_to_commit=true)
    - INDIRECT_ONLY → 'improving' (kein direktes Signal-Target)
    """

    verification_tool: Literal["drift_nudge", "drift_shadow_verify"] = "drift_nudge"
    """Routing-Signal:
    - edit_kind in CROSS_FILE_RISKY_EDIT_KINDS → 'drift_shadow_verify'
    - alle anderen → 'drift_nudge'
    """

    verification_params: dict[str, str] = Field(default_factory=dict)
    """Direkt an das Verifikations-Tool weiterzuleitende Parameter:
    - task_signal: str
    - task_edit_kind: str
    - task_context_class: 'production' | 'test'
    Ermöglicht automatisches Outcome-Recording in der RepairTemplateRegistry (ADR-065)."""
```

### Ableitungsregeln

#### `direction_required` aus `repair_maturity`

| repair_maturity | direction_required | Erfolgsbedingung |
|---|---|---|
| `VERIFIED` | `"resolved"` | `nudge.direction != "regressing"` UND `resolved_signal` in `nudge.resolved_findings` |
| `EXPERIMENTAL` | `"improving"` | `nudge.direction == "improving"` UND `nudge.safe_to_commit == true` |
| `INDIRECT_ONLY` | `"improving"` | `nudge.direction == "improving"` UND `nudge.safe_to_commit == true` |

#### `verification_tool` aus `edit_kind`

```python
from drift.fix_intent import CROSS_FILE_RISKY_EDIT_KINDS

def _verification_tool_for(edit_kind: str) -> Literal["drift_nudge", "drift_shadow_verify"]:
    return "drift_shadow_verify" if edit_kind in CROSS_FILE_RISKY_EDIT_KINDS else "drift_nudge"
```

`CROSS_FILE_RISKY_EDIT_KINDS` (aus `src/drift/fix_intent.py`):
`remove_import`, `relocate_import`, `reduce_dependencies`, `extract_module`,
`decouple_modules`, `scope_prompt_boundary`, `delete_symbol`, `rename_symbol`

---

## Auto-Verification-Routing nach `patch_commit`

Nach `patch_commit` (ADR-074, Phase 3 der Patch-Transaktion) löst der Router automatisch
das Verifikations-Tool aus — **ohne manuellen Aufruf durch den Agenten**:

```
patch_commit(task_id, session_id, accepted=True)
    ↓
_load_verification_spec(task_id, session)   # aus PatchIntent (Option B) oder RepairTask (Option A)
    ↓
if spec.verification_tool == "drift_shadow_verify":
    shadow_verify(scope_files=spec.scope_files, ...)
else:
    nudge(
        changed_files=intent.declared_files,
        task_signal=spec.verification_params["task_signal"],
        task_edit_kind=spec.verification_params["task_edit_kind"],
        task_context_class=spec.verification_params.get("task_context_class", "production"),
    )
    ↓
_evaluate_verification_result(result, spec)  # prüft direction_required
    ↓
PatchVerdict.auto_verification_result: VerificationOutcome  # neu: "passed" | "failed" | "skipped"
```

`PatchVerdict` erhält ein neues Feld `auto_verification_result`:
- `"passed"` — Erfolgsbedingung aus `direction_required` erfüllt
- `"failed"` — Erfolgsbedingung nicht erfüllt; `PatchStatus` → `REVIEW_REQUIRED`
- `"skipped"` — kein `VerificationSpec` vorhanden (backward-compat)

---

## Explizit nicht umgesetzt

- **Kein neues Signal** — `VerificationSpec` ist reine Modell-/Router-Änderung
- **Kein Scoring-Einfluss** — Verifikationsergebnisse fließen nur in Outcome-Recording, nicht in Scores
- **Kein Hard-Enforcement** — Advisory-Modell aus ADR-074 bleibt erhalten; `REVIEW_REQUIRED` blockiert nicht
- **Keine Garantie vollständiger Determinismus** — Scope: nur Tasks mit `automation_fit=HIGH`, `change_scope=LOCAL`, `review_risk=LOW`
- **Kein Breaking Change** an `AgentTask` — `VerificationSpec` wird additiv eingeführt
- **Kein neues CLI-Subcommand** — Auto-Routing passiert intern im `patch_commit`-Router
- **Kein Schema-Update für `drift.output.schema.json`** in dieser Phase (betrifft nur `fix_plan`-Output)

---

## Begründung

### Warum `VerificationSpec` statt erweiterter Freitext-`acceptance_criteria`?

`acceptance_criteria: list[str]` kann nicht von drift selbst ausgewertet werden. Drift kann nur
dann automatisch verifizieren, wenn es weiß, **welches Signal**, **welches Symbol** und **welche
Mindestverbesserung** erwartet wird. Ein geschlossenes Enum (`direction_required`) ist kleiner,
sicherer und testbarer als NLP-Parsing von Textstrings.

### Warum gestufte Verifikation nach `repair_maturity`?

`repair_maturity` ist bereits auf `AgentTask` vorhanden und semantisch die korrekte Quelle für
Verifikationserwartungen. `VERIFIED`-Repairs haben hohe Template-Confidence (≥ 3 improving
outcomes in `RepairTemplateRegistry`) — hier ist `"resolved"` realistisch. `EXPERIMENTAL`-Repairs
haben niedrigere Confidence — hier ist `"improving"` die sichere Grenze, die false-negatives
vermeidet.

### Warum `CROSS_FILE_RISKY_EDIT_KINDS` → `drift_shadow_verify`?

`drift_nudge` ist file-scope-bounded: Es scannt nur geänderte Dateien. Cross-file-risky edits
(z. B. `rename_symbol`, `extract_module`) können Regressions in unveränderten Konsumenten
erzeugen. `drift_shadow_verify` (ADR-064) ist explizit für diesen Fall gebaut.

### Alternativen verworfen

| Alternative | Ablehnungsgrund |
|---|---|
| LLM-generierte Verifikationskriterien zur Agentenlaufzeit | Halluzinationsrisiko; nicht deterministisch; erhöhte Latenz |
| Server-seitiges Hard-Enforcement bei `FAILED` | Bricht Agent-Autonomie; schwer rückgängig zu machen |
| Verifikation nur über CI-Gate (kein In-Loop) | Feedbackzyklus zu lang für iterative Fix-Loops |
| Eigenes `verification_tool: "drift_scan"` | Zu teuer; `drift_nudge` und `drift_shadow_verify` sind die richtigen Werkzeuge für inkrementelle Verifikation |

---

## Konsequenzen

### Positiv

- **Vollautonomie-Schwelle erreichbar** für Tasks mit `automation_fit=HIGH` + `repair_maturity=VERIFIED`:
  Agent führt Task aus → `patch_commit` → auto-nudge → `VerificationOutcome.passed` → fertig
- **Outcome-Recording automatisch befüllt** — `verification_params` in `VerificationSpec`
  triggern `task_signal`/`task_edit_kind` in `nudge`, sodass `RepairTemplateRegistry`
  kontinuierlich lernt
- **`PatchVerdict` wird richer** — `auto_verification_result` ist maschinenlesbar für CI-Gates
  (`if verdict.auto_verification_result == "failed": require_review`)
- **Kein Breaking Change** — bestehende Workflows ohne `VerificationSpec` landen in `"skipped"`

### Trade-offs

- `VerificationSpec` muss bei neuen Signalen gepflegt werden (Reviewer-Checkliste, analog `edit_kind`)
- `direction_required="resolved"` kann false-negative sein, wenn ein anderes Fix im gleichen
  Session-Kontext das Finding bereits resolved hat → `resolved_symbol` als Scope-Einschränkung
  macht dies robuster, aber nicht perfekt
- Option B (Stack-Extension) erhöht `PatchIntent`-Komplexität leicht; Option A (neues Modell)
  erhöht Agenten-Onboarding-Last

---

## Validierung

```bash
# Unit-Tests für VerificationSpec-Ableitung und Routing-Logik
pytest tests/test_verification_spec.py -v

# Regression-Guard: bestehende patch_commit-Flows dürfen nicht brechen
pytest tests/test_patch_engine.py tests/test_mcp_router_patch.py -v --tb=short

# Full suite ohne Smoke
pytest tests/ --tb=short --ignore=tests/test_smoke_real_repos.py -m "not slow" -q -n auto --dist=loadscope

# Drift-Selbstanalyse
drift analyze --repo . --format json --exit-zero
```

**Lernzyklus-Erwartung (§10 Policy):**

| Verifikationsebene | Erwartetes Ergebnis | Zeitpunkt |
|---|---|---|
| `VERIFIED`-Tasks: `direction_required="resolved"` erfolgreich ausgewertet | `bestätigt` | nach erster Field-Test-Session mit auto-routing |
| Outcome-Recording via `verification_params` in `RepairTemplateRegistry` korrekt befüllt | `bestätigt` | nach 3+ auto-verified Tasks |
| False-negative bei `resolved_symbol=None` (anderer Fix resolved zuerst) | `unklar` → `resolved_symbol` Pflichtfeld für VERIFIED? | nach Analyse von Mismatches |
| Option B vs. Option A: `PatchIntent`-Komplexität akzeptabel | `bestätigt` oder `zurückgestellt` | nach Maintainer-Review |

---

## Referenzen

- [ADR-063](ADR-063-fix-intent-structured-contract.md) — `fix_intent` Advisory-Contract (Basis)
- [ADR-064](ADR-064-shadow-verify-cross-file-risky-edits.md) — `drift_shadow_verify` für CROSS_FILE_RISKY
- [ADR-065](ADR-065-repair-template-registry.md) — `RepairTemplateRegistry` Outcome-Recording
- [ADR-072](ADR-072-remediation-memory.md) — Remediation Memory (komplementär)
- [ADR-074](ADR-074-patch-engine.md) — Patch Engine, `PatchIntent.acceptance_criteria` Lücke
- [ADR-075](ADR-075-remediation-contract-as-first-class-concept.md) — `root_cause` als First-Class-Concept
- [ADR-076](ADR-076-patch-writer-auto-apply.md) — `fix_apply` ohne Auto-Verification
- `src/drift/fix_intent.py` — `CROSS_FILE_RISKY_EDIT_KINDS`, `EDIT_KIND_FOR_SIGNAL`
- `src/drift/models/_patch.py` — `PatchIntent`, `PatchVerdict`, `PatchStatus`
- `src/drift/models/_agent.py` — `AgentTask`, `repair_maturity`, `to_patch_intent()`
- `src/drift/api/fix_apply.py` — fehlende Auto-Nudge-Integration
- `src/drift/api/nudge.py` — `task_signal`, `task_edit_kind`, `task_context_class`
- `src/drift/mcp_router_patch.py` — `run_patch_commit()` Erweiterungspunkt
- `benchmark_results/v2.14.0_patch_engine_feature_evidence.json`
- METR SWE-bench Analyse (2026-03-10): https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/

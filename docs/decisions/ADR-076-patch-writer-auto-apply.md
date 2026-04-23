---
id: ADR-076
status: proposed
date: 2026-04-19
supersedes:
---

# ADR-076: PatchWriter — Ausführbare Auto-Patches für `add_docstring` und `add_guard_clause`

## Kontext

Das Patch-Engine-Fundament (ADR-063–065, ADR-074) stellt maschinenlesbare Repair-Tasks,
Scope-Kontrolle via `patch_begin/check/commit` und eine Repair-Template-Registry bereit.
Alle Findings enden jedoch weiterhin in Text-Empfehlungen (`fix`-Feld, `action`-String).
Agenten und Nutzer müssen den eigentlichen Code-Edit selbst erzeugen.

Die Handlungsfähigkeit (POLICY.md §5.3) ist damit auf Planung beschränkt.
Ein `PatchWriter`-Modul würde für eine erste Teilmenge von Edit-Kinds (LOCAL,
`automation_fit=HIGH`) tatsächliche Source-Code-Edits erzeugen und anwenden.

## Entscheidung

Ein neues Subpackage `src/drift/patch_writer/` wird eingeführt:

- **`_base.py`**: abstrakte Klasse `PatchWriter` mit `can_write(finding) → bool` und
  `generate_patch(finding, source) → str | None`; `PatchResult` dataclass mit `status`,
  `diff`, `edit_kind`, `file_path`, `reason`.
- **`_registry.py`**: `get_writer(edit_kind) → PatchWriter | None` Lookup-Funktion.
- **`_add_docstring.py`**: libcst-Transformer für `EDIT_KIND_ADD_DOCSTRING` (EDS-Signal);
  fügt Stub-Docstring `"""TODO: document <symbol>."""` ein wenn kein Docstring existiert.
- **`_add_guard_clause.py`**: libcst-Transformer für `EDIT_KIND_ADD_GUARD_CLAUSE` (GCD-Signal);
  generiert `if <param> is None: raise TypeError(...)` für Parameter aus `finding.metadata`.

Eine neue API-Funktion `src/drift/api/fix_apply.py` orchestriert:
1. Git-State-Check (sauberer Arbeitsbaum erforderlich)
2. Filter auf `automation_fit=HIGH AND change_scope=LOCAL AND review_risk=LOW`
3. PatchWriter → `patch_begin/check/commit`-Protokoll → Rollback bei ROLLBACK_RECOMMENDED
4. Outcome-Recording zur Repair-Template-Registry

`drift fix-plan` erhält drei neue Flags: `--apply`, `--dry-run`, `--yes`.

**Explizit nicht in scope:**
- TS/JS-Docstrings (v1 Python-only)
- Weitere Edit-Kinds als `add_docstring` und `add_guard_clause`
- Automatische Commits nach dem Apply
- MCP-autonomous-apply ohne User-Intent

## Begründung

**libcst** gegenüber stdlib `ast` + `ast.unparse`: libcst ist Whitespace-sicher und
verliert keine Kommentare, Formatierung oder Unicode-Literale. Der Verlust durch
`ast.unparse` wäre bei Production-Code nicht akzeptabel.

**Opt-in-Dep** (`pip install drift[autopatch]`) statt Pflicht-Dep: minimale Installationsgröße
für die Mehrheit der Nutzer, die kein Apply benötigen. Lazy-Import mit klar verständlicher
Fehlermeldung (`pip install drift[autopatch]`).

**Nur LOCAL, automation_fit=HIGH, review_risk=LOW**: minimales Blast-Radius. Diese Teilmenge
umfasst die zwei häufigsten und sichersten Edit-Kinds. Cross-file-risky Edits bleiben
agent-only und erfordern explizite shadow-verify.

**Verworfen: zeilenbasiertes Patching**: fragil bei Einrückung, Continuation-Lines und
Dekoratoren. Nicht vertretbar für Production-Code.

## Konsequenzen

- Neue Pflicht-Dep für `drift[autopatch]`: libcst ≥ 1.0
- §18-Pflichten: neuer File-Write-Pfad → STRIDE (neue Trust-Boundary), FMEA (neue FMs),
  Risk-Register-Einträge erforderlich
- `repair_templates/templates.json` erhält Seed-Daten für GCD `add_guard_clause`
  (bisher improving_count=0 / regressing_count=0 — nach Fixture-Tests initial zu befüllen)
- `drift fix-plan --dry-run` ist Opt-out-free (keine File-Writes, nur Diff-Preview) —
  safe für CI-Pipelines
- Rollback-Protokoll: wenn `patch_check` ROLLBACK_RECOMMENDED liefert, wird Original-Datei
  aus Speicher wiederhergestellt; Git-Working-Tree bleibt sauber

## Validierung

- TDD: Failing-Test zuerst, dann Minimal-Implementierung. Kein Produktions-Code ohne
  vorherig gescheiterten Test.
- Precision: `pytest tests/test_patch_writer*.py tests/test_fix_apply_integration.py`
- Rollback: erzwungener ROLLBACK_RECOMMENDED-Pfad → Original-Datei unverändert
- Smoke: `drift fix-plan --dry-run --repo . --signal EDS` → Diff-Preview, keine Writes
- Policy §10: Ergebnis nach Integration: bestätigt | widerlegt | unklar | zurückgestellt

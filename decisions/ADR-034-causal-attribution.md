---
id: ADR-034
status: proposed
date: 2026-04-09
supersedes:
---

# ADR-034: Causal Attribution — Finding-Level Drift Provenance

## Kontext

Drift erkennt heute *was* driftet, beantwortet aber nicht *warum* und *wer* es
verursacht hat. Teams können Drift-Findings keinem konkreten Commit, Autor oder
Branch zuordnen. Das verhindert gezielte Nachverfolgung und macht es unmöglich,
systematische Muster zu erkennen (z. B. "Nach AI-assisted PRs steigt der
Drift-Score konsistent um 12 Punkte").

**Zentrale Unsicherheit:** Ohne Kausalzuordnung bleibt unklar, ob Drift-Probleme
durch einzelne Änderungen, schleichende Erosion oder spezifische Workflows
(AI-Coding, Feature-Branches) entstehen.

## Entscheidung

### Was getan wird

Attribution wird als **Post-Detection-Enrichment** implementiert — kein neues
Signal, sondern eine Cross-Cutting-Anreicherung aller bestehenden Findings:

1. **Neue Ingestion-Schicht** `src/drift/ingestion/git_blame.py` — parst
   `git blame --porcelain -L` für zeilenexakte Zuordnung pro Finding
2. **Enrichment-Orchestrator** `src/drift/attribution.py` — verknüpft Blame-
   Daten mit Findings, ermittelt primären Verursacher-Commit und -Autor
3. **Typisiertes Datenmodell** `Attribution` als eigenes Feld auf `Finding`
4. **Opt-in-Konfiguration** `attribution.enabled: false` (Default) mit
   konfigurierbarem Timeout, Worker-Count und Cache

### Was explizit nicht getan wird

- **Kein eigenständiges Signal**: Attribution erkennt kein Kohärenzproblem,
  daher kein Score-Impact und keine Verzerrung des Composite Scores
- **Kein Default-on**: Blame-Kosten (Subprocess pro Finding) werden nicht allen
  Nutzern auferlegt, bis Performance auf großen Repos validiert ist
- **Keine Author-Aggregation in Phase 1**: Team-Pattern-Analyse
  (`AuthorDriftProfile`, `BranchDriftProfile`) folgt in separatem PR nach
  Validierung der Grundinfrastruktur

## Begründung

### Enrichment statt Signal

Attribution erkennt kein Kohärenzproblem — es reichert bestehende Findings mit
Provenance-Daten an. Als Signal würde es den Composite Score verzerren
(Autoren-Diversität ist kein Drift-Indikator). Als Enrichment profitieren
hingegen alle 24 Signale automatisch, ohne Score-Logik zu ändern.

### `git blame --porcelain` statt Log-Heuristik

`git blame` liefert zeilenexakte Zuordnung. Die Alternative (nur aus
`git log --numstat` schätzen, welcher Commit die Finding-Zeilen erzeugt hat) wäre
ungenauer und führt zu Attribution-Fehlern bei Files mit hoher Churn-Rate.

### Eigenes typisiertes Feld statt nur `metadata`

`Finding.attribution: Attribution | None` statt `metadata["attribution"]`:
- Konsistente Serialisierung in allen Output-Formaten (JSON, SARIF, Rich)
- Autovervollständigung und Typ-Checks in Downstream-Konsumenten
- Schema-Evolution über Dataclass statt untypisiertes Dict

### Opt-in mit Performance-Guard

`git blame` erzeugt einen Subprocess pro File (nicht pro Finding — Findings im
selben File teilen sich den Blame-Result). Performance-Budget:
- ThreadPool mit max 4 Workern (konfigurierbar)
- 3s Timeout pro File (konfigurierbar)
- LRU-Cache auf `(file_path, content_hash)`
- Files ohne `start_line` werden übersprungen

## Konsequenzen

### Positive Konsequenzen

- Findings werden handlungsfähiger: "Commit a3f2 von X hat diesen Guard-Clause-
  Deficit eingeführt, 2h nach Merge von feature/llm-refactor"
- Teams können Muster identifizieren (AI-assisted PRs, spezifische Branches)
- SARIF-Output wird um Attribution-Properties angereichert (IDE-Integration)
- Grundlage für zukünftige Team-Aggregation und Branch-Pattern-Analyse

### Trade-offs

- **Performance-Overhead**: 1-5s zusätzlich für typische Repos (500 Findings),
  daher Opt-in
- **Neue Trust Boundary**: `git blame` als Subprocess-Aufruf → STRIDE-Update
  erforderlich
- **Branch-Hint ungenau**: `git blame` liefert keinen Branch-Namen; Heuristik
  aus Merge-Commit-Messages (`Merge branch 'xxx'`) ist bestmöglich aber nicht
  perfekt
- **Schema-Bump**: `Finding`-Dataclass bekommt neues Feld → Output-Schema 1.2

## Validierung

- [ ] Unit-Tests: Blame-Parsing (Porcelain-Format), Timeout, Cache-Hit/Miss
- [ ] Unit-Tests: Enrichment mit/ohne Line-Range, Fallback bei Blame-Fehler
- [ ] Integration-Test: Pipeline-Lauf mit `attribution.enabled: true` auf
      `tmp_repo` Fixture — Findings haben plausible Attribution
- [ ] Performance: Attribution-Overhead < 3s für 500 Findings auf mittlerem Repo
- [ ] Output: JSON-Schema, SARIF-Konformität, Rich-Terminal-Rendering
- [ ] `make check` bestanden, Precision/Recall unverändert
- [ ] Audit-Artefakte: `stride_threat_model.md` + `risk_register.md` aktualisiert

### Referenzierte Artefakte

| Artefakt | Pflicht-Update |
|----------|---------------|
| `audit_results/stride_threat_model.md` | Ja — neuer Input-Pfad (git blame) |
| `audit_results/risk_register.md` | Ja — neues Feature mit Trust-Boundary |
| `tests/test_attribution.py` | Neu — Unit-Tests |
| `benchmark_results/` | Feature-Evidence bei feat:-Commit |

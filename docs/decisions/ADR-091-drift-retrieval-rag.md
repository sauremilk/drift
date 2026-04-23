---
id: ADR-091
status: proposed
date: 2026-04-22
supersedes:
relates-to: ADR-031, ADR-084, ADR-089, ADR-090
---

# ADR-091: Drift-Retrieval-RAG — Deterministische Fakten-Grounding-Schicht für Agenten

## Kontext

Coding-Agenten (Copilot, Claude Code, Cursor), die drift über den MCP-Server
konsumieren, treffen Aussagen über drifts Policy, Signale, ADR-Entscheidungen,
Audit-Ergebnisse und Benchmark-Evidence regelmäßig frei-assoziierend statt
aus verifizierten Quellen. Das untergräbt zwei der drei Drift-Tugenden aus
POLICY §3.2: **Glaubwürdigkeit der Ergebnisse** und **Verständlichkeit der
Befunde**.

Bestehende Oberflächen decken das nicht ab:

- `drift_explain` erklärt Signale generisch, nicht zitatfähig.
- `drift_map` / `drift_steer` liefern Architekturkontext des analysierten
  Repos, nicht drifts eigene Entscheidungsbasis.
- `llms.txt` ist statisch, nicht abfragbar, und die meisten Agenten lesen
  es nicht vollständig.
- `drift.agent.prompt.md` führt Contracts auf, aber keine zitierbaren
  Fakten über die Contracts selbst.

POLICY §13 fordert „technische Erklärbarkeit, Reproduzierbarkeit und klare
Benennung des betroffenen Orts" — exakt das brauchen Agenten-Aussagen über
drift, nicht nur drift-Findings über Code.

ADR-031 hat **kNN-Semantic-Search explizit verworfen**
(„Aufwand L, Nutzen unklar"). Diese Entscheidung bleibt bindend für den
Detection-Path. Sie verbietet nicht, eine **deterministische lexikalische**
Retrieval-Schicht außerhalb der Signal-Pipeline als Informations-Bereitstellung
für Agenten einzuführen.

## Entscheidung

Drift erhält eine **deterministische lexikalische Retrieval-Schicht** unter
`src/drift/retrieval/`, die drifts eigene Faktenquellen indexiert und über
zwei MCP-Tools zitierbar verfügbar macht:

1. **`drift_retrieve(query, top_k=5, kind=None, signal_id=None)`** —
   BM25-Suche über den Korpus, liefert Chunks mit stabiler `fact_id`,
   Quellpfad, Zeilenbereich, Auszug und SHA-256-Anker.
2. **`drift_cite(fact_id)`** — Expandiert eine Fact-ID zum vollständigen
   Chunk für wörtliches Zitieren; löst über Migration-Registry auf.

**Korpus (MVP):**

| Quelle | Chunk-Strategie | Fact-ID-Präfix |
|---|---|---|
| `POLICY.md`, `ROADMAP.md` | Heading + Paragraph | `POLICY#S<n>.p<m>`, `ROADMAP#S<n>.p<m>` |
| `docs/decisions/ADR-*.md` | Abschnitt (Kontext / Entscheidung / Begründung / Consequences) | `ADR-<n>#<section>` |
| `audit_results/*.md` | Tabellen-Zeile mit Spalten-Kontext | `AUDIT/<file>#<row-id>` |
| `src/drift/signals/*.py` | Class-Docstring + `reason()`/`fix()` via AST | `SIGNAL/<signal_id>#<rationale\|weight\|scope>` |
| `benchmark_results/v*_feature_evidence.json` | flache JSON-Records | `EVIDENCE/v<version>#<key>` |

**Fact-ID-Stabilität (Option A):** IDs sind strukturbasiert und lesbar.
Eine append-only Registry `docs/decisions/fact_id_migrations.jsonl` leitet alte
IDs bei legitimem Umbenennen auf neue IDs weiter. `drift_cite` löst
transitiv auf. Snapshot-Test in `tests/test_retrieval_corpus.py` sichert
Stabilität.

**Korpus-Refresh (Option A):** Beim ersten MCP-Call pro Session prüft
der Corpus-Builder `mtime + sha256` aller Quellen gegen ein
`corpus_manifest.json` (im User-Cache-Dir analog `EmbeddingCache`).
Nur bei Mismatch: inkrementeller Rebuild der betroffenen Chunks.

**Grounding-Kontrakt (Instruction-Level):** Neue Instruction
`.github/instructions/drift-rag-grounding.instructions.md` mit
`applyTo: "**"` verpflichtet Agenten, Behauptungen über drifts Policy,
Signale, ADRs, Audit-Ergebnisse oder Benchmark-Evidence vor der Ausgabe
über `drift_retrieve` zu grounden und mindestens eine `fact_id` zu zitieren.
Hard-Enforcement im MCP-Server wird bewusst **nicht** eingeführt — der
Vertrag läuft über Copilot-Instructions-Discovery, analog zum bestehenden
Gate-Mechanismus in `drift-policy.instructions.md`.

**Determinismus-Garantie:** Gleicher Query + gleicher `corpus_sha256` →
gleiche Ergebnis-Reihenfolge. Tie-Breaking über `fact_id` lexikografisch,
nie über Insertion-Order. Test-gesichert in `tests/test_retrieval_search.py`.

## Begründung

**Distribution-Support-Framing:** Drift ist in der Distribution-Phase
(Q2 2026, POLICY §14 + ROADMAP), die „bugfixes only" fordert. Dieses
Feature wird trotzdem zugelassen, weil es **Adoption senkt** und
**Glaubwürdigkeit erhöht** (POLICY §8 Zulassungskriterien Glaubwürdigkeit
+ Einführbarkeit): Externe Adopter (Zielgruppe Z1/Z2) prüfen drift vor
Einsatz über Agenten-Anfragen („Was ist ein PFS-Signal?", „Warum ist MDS
gewichtet 0.55 AST + 0.35 Embedding?"). Ohne Retrieval-Schicht halluzinieren
Agenten; mit Retrieval zitieren sie aus der Projektdokumentation. Das
senkt die Einstiegshürde für Epoche A (Adoption) messbar.

**Lexikalisch statt semantisch (MVP):** ADR-031 hat Semantic-Search
verworfen. Lexikalische BM25 ist deterministisch, reproduzierbar, ohne
neue Hard-Dep implementierbar (~80 LoC interne Implementation) und
policy-konform (§1.3 Reproduzierbarkeit).

**Instruction-Gate statt Server-Enforcement:** Ein ungecitet-Reject im
MCP-Server würde legitime Agenten-Nutzungen (Debugging, Exploration)
blockieren und neue Fehlerpfade schaffen. Instruction-Level ist konsistent
mit dem bestehenden Drift-Policy-Gate.

**Strukturbasierte IDs statt Content-Hashes:** Agent-Aussagen wie
„gemäß `POLICY#S8.p3`" sind für menschliche Reviewer nachvollziehbar;
opake Hashes wie `fact#a3f29b...` sind es nicht. Renaming-Registry löst
das Stabilitätsproblem bei Dokument-Umstrukturierung.

**Abgrenzung zu ADR-031 explizit:** ADR-031 verbietet kNN-Semantic-Search
**in der Detection-Pipeline**. Diese ADR führt Retrieval **außerhalb**
der Pipeline ein (eigenes Modul, keine Findings, kein Score-Einfluss,
keine ArchGraph-Mutation). ADR-031 bleibt unberührt.

**Explizit nicht Teil dieser Entscheidung:**

- Semantische Embeddings oder kNN-Re-Ranking — Phase 2 unter separater
  Gegen-ADR mit Evidence (Precision-Gain ≥ 15 % gegen BM25).
- Hard-Enforcement über MCP-Server-Reject bei ungecitet Antworten.
- Öffentliches CLI-Subcommand `drift retrieve` für End-User.
- Target-Repo-Fakten (nur drifts eigener Korpus).
- Skills-Auto-Generierung mit Fact-Sheets.
- Korpus-Quellen über MVP-Scope hinaus (`docs/`, `docs-site/`).

## Konsequenzen

**Positive:**

- Agenten-Antworten über drift werden zitatfähig und auditierbar.
- Neue Zielgruppe (externe Adopter) erhält selbstbedienbare
  Entscheidungsgrundlage über Coding-Agenten.
- Policy-Konsistenz: Grounding-Instruction ergänzt bestehendes
  Policy-Gate (`drift-policy.instructions.md`) ohne Duplikation.

**Negative / Risiken:**

- **Neues Trust-Boundary** „Retrieval Corpus Loader": STRIDE-Assessment
  erforderlich (Tampering über manipulierten Cache, Information-Disclosure
  bei nicht-öffentlichen Inhalten). Mitigation: SHA-Anker im Manifest,
  Cache nur im User-Dir, Korpus enthält nur Public-Repo-Inhalte.
- **Fact-ID-Drift** bei Dokument-Restrukturierung: Mitigation via
  Migration-Registry + Snapshot-Test (siehe FMEA-Zeile).
- **Agent-Compliance-Risiko:** Instruction-Gate ist nicht hart durchsetzbar.
  Mitigation: Review-Stichprobe auf Zitate bei PR-Handoff; Verschärfung auf
  Server-Enforcement wird beobachtet und ggf. in Folge-ADR nachgezogen.

**Audit-Artefakt-Pflicht (POLICY §18):** Umsetzung erfordert Updates in
`audit_results/fmea_matrix.md`, `stride_threat_model.md`, `risk_register.md`,
`fault_trees.md` (FT-3 Erweiterung: Retrieval-Zweig).

**Feature-Evidence-Pflicht:** `benchmark_results/v_next_drift_retrieval_rag_feature_evidence.json`
mit Korpus-Stats, Gold-Set-Precision@5 ≥ 80 %, Determinismus-Hash, Latenz.

## Abnahmekriterien

1. `drift_retrieve("POLICY Zulassungskriterien")` liefert `POLICY#S8.*` als
   Top-Treffer.
2. `drift_cite` auf eine beliebige Fact-ID liefert exakten Chunk, dessen
   SHA-256 dem Manifest entspricht.
3. Zwei aufeinanderfolgende Corpus-Builds auf identischem Input erzeugen
   identischen `corpus_sha256`.
4. Gold-Set-Precision@5 ≥ 80 % auf mindestens 15 handkuratierten
   Query→Fact-ID-Paaren.
5. Umbenennung einer ADR-Section aktualisiert die Fact-ID und fügt
   Migration-Registry-Eintrag hinzu; alter ID-Aufruf via `drift_cite`
   resolved weiterhin.
6. Audit-Artefakte + Feature-Evidence grün in `make gate-check COMMIT_TYPE=feat`.

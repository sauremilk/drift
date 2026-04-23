---
id: ADR-087
status: proposed
date: 2026-04-22
supersedes:
scope:
  - "src/drift/blast_radius/**"
  - "scripts/check_blast_radius_gate.py"
  - "scripts/validate_adr_frontmatter.py"
  - "docs/decisions/**"
  - ".github/skills/guard-*/**"
  - "hooks/pre-push"
  - ".github/instructions/drift-push-gates.instructions.md"
criticality: high
---

# ADR-087: Blast-Radius-Engine (K1)

## Kontext

Drift erkennt heute architektonische Erosion nach dem Edit (`nudge`, `diff`,
`scan`) und liefert punktuelle Leitplanken pro Datei (`steer`, `brief`,
Guard-Skills). Die Closed-Loop-Lücke "Sichere Ausführung / Delegation" bleibt:
Weder Nudge (lokale Richtung) noch Guardrail (einzelne Datei) prüfen, ob ein
geplanter oder gerade durchgeführter struktureller Edit **existierende ADRs,
Leitplanken, Policy-Gates oder abhängige Module invalidiert**.

In der Praxis bedeutet das:

- Ein Agent kann die Interface-Signatur eines Signals ändern, ohne dass ADR-040
  oder ADR-019 als potenziell ungültig markiert werden.
- Ein Umbenennen von `src/drift/signals/` würde 13 Guard-Skills und mehrere
  ADR-Scopes invalidieren, ohne dass dies vor dem Commit sichtbar wäre.
- Pre-Push-Gates (§7, §18) triggern erst am Push, nicht am Plan-Zeitpunkt.

Der vorhandene **ArchGraph** (`arch_graph.json`, `src/drift/arch_graph/`) kennt
Module-Dependencies, ArchDecisions und Hotspots. Der vorhandene **adr_scanner**
kennt textbasiertes ADR-Relevance-Matching. Beide decken Blast-Radius aber nur
partiell ab, weil ADR-Scope nicht strukturiert hinterlegt ist und Guard-Skills
keine maschinenlesbare `applies_to`-Bindung haben.

## Entscheidung

Drift erhält eine **Blast-Radius-Engine (K1)**, die vor jedem strukturellen
Edit die Menge aller transitiv invalidierten ADRs, Guard-Skills, ArchDecisions
und abhängigen Module berechnet und in vier Oberflächen wirksam macht:

1. **Neues Paket `src/drift/blast_radius/`** mit Pydantic-Modellen
   (`BlastImpact`, `BlastReport`) und vier Analyzern (Arch, ADR, Skill, Policy).
2. **Neues MCP-Tool `drift_blast_radius`** (A2A-Skill `blast_radius`), das auf
   Basis eines Diffs (oder `changed_files`) einen vollständigen `BlastReport`
   liefert.
3. **Versioniertes Artefakt** `blast_reports/<yyyymmdd_hhmmss>_<short_sha>.json`
   mit Schema-Version, `generated_by`-Block und reproduzierbarer Ancestry.
4. **Pre-Push-Gate 9 ("Blast-Radius")**, das bei Commits in `src/drift/**`,
   `docs/decisions/**`, `POLICY.md`, `.github/skills/**` einen gültigen Report für
   den Push-HEAD verlangt und bei `severity=critical` ohne Maintainer-Ack in
   `blast_reports/acks/<short_sha>.yaml` hart blockiert.

Zur strukturierten Invalidierung werden zwei optionale ADR-Frontmatter-Felder
eingeführt:

- `scope: list[str]` — Glob-Patterns relativ zu Repo-Root (z. B.
  `src/drift/signals/**`). Leer → Fallback auf textbasierten `adr_scanner`.
- `criticality: critical | high | normal` — Markierung durch Maintainer.
  `critical` triggert harte Pre-Push-Blockade.

Analog erhalten Guard-Skills (`.github/skills/guard-*/SKILL.md`) optional
`applies_to: list[str]`. Fehlt das Feld, leitet der Skill-Analyzer die Scope
aus dem Skill-Namen ab (`guard-src-drift-signals` → `src/drift/signals`).

## Explizit nicht getan

- Keine automatische ADR-Generierung oder Supersedes-Vorschläge durch Blast-Radius.
- Kein Live-Blast pro Datei-Speicherung (bleibt Nudge-Domäne).
- Kein Backfill aller 86 ADRs in dieser Iteration — nur ADRs mit direktem
  Bezug zu Kern-Oberflächen (`signals/`, `scoring/`, `ingestion/`, `output/`,
  `policy/`) erhalten `scope`/`criticality` im Initial-Commit.
- Kein Auto-Write in `audit_results/` aus dem Blast-Pfad.
- Kein CLI-Command in dieser Iteration (nur MCP-Skill und Hook-Script).
- Agent darf `criticality: critical` in ADRs **nicht** selbst setzen und darf
  keine Ack-Dateien unter `blast_reports/acks/` erzeugen
  (Delegation-Boundary aus `.github/copilot-instructions.md`).

## Begründung

Alternativen erwogen:

- **Nur MCP-Tool ohne Pre-Push-Gate.** Verworfen: Closed-Loop-Lücke bliebe, weil
  der Agent das Tool umgehen kann. Ein Sicherheits-Mechanismus ohne Durchsetzung
  ist Placebo.
- **Komplett textbasiert auf `adr_scanner` ohne Frontmatter-Scope.** Verworfen:
  Precision zu niedrig (ADR mit Token "signals" erzeugt Falschpositive bei
  völlig unrelated Signal-Kontext).
- **ArchDecisions aus `arch_graph.json` als einzige Scope-Quelle.** Verworfen:
  Benötigt ein Mapping ADR↔ArchDecision, das heute nicht existiert und ein
  eigenes ADR erfordern würde.
- **Nudge-Erweiterung um Blast-Semantik.** Verworfen: Nudge ist auf
  Sub-Sekunden-Latenz optimiert (file-local); Blast-Radius braucht ArchGraph-
  und ADR-Traversal und ist per se langsamer (<5s Budget).

Das gewählte Design trennt die drei Schichten klar:

- **Nudge** = Richtung, lokal, schnell (<1s).
- **Guardrail / steer** = pro Datei, pre-edit Kontext.
- **Blast-Radius** = transitive Systemfolgen, pre-commit, mit Gate.

## Konsequenzen

**Positiv**
- Closed-Loop-Lücke "Sichere Ausführung / Delegation" wird geschlossen.
- Maintainer erhalten deterministische Audit-Kette: jeder strukturelle Commit
  hat ein Blast-Artefakt mit Ancestry.
- ADR-Frontmatter wird schrittweise strukturierter, ohne Big-Bang-Migration.

**Negativ / Risiken**
- Falsch-Positiv-Lähmung: Zu breite Scope-Globs blockieren Entwickler. Gegenmaßnahme:
  `critical`-Tag ist opt-in durch Maintainer; Audit-Pflicht bei jeder Hochstufung.
- Performance bei großen Graphen: Budget 5s (Median) / 10s (P95). Gegenmaßnahme:
  `BlastReport.degraded=True` statt Exception; Gate blockiert bei `degraded`
  nicht hart.
- Bypass-Missbrauch: `DRIFT_SKIP_BLAST_GATE=1` wird geloggt und taucht in
  Risk-Register auf (STRIDE: Elevation of Privilege).

## Validierung

Konkrete Checks:

```bash
pytest tests/test_blast_radius_core.py tests/test_blast_radius_mcp.py tests/test_blast_radius_gate.py -v
python scripts/validate_adr_frontmatter.py
python scripts/check_blast_radius_gate.py --ref HEAD~1 --head HEAD
drift-analyzer --version                  # sichtbar im Report
```

Precision/Recall-Ziele (Policy §13):

- ADR-Invalidierungs-Precision ≥ 0.90 gegen kuratierte Diff-Fixtures.
- Guard-Skill-Invalidierungs-Recall ≥ 0.80 für Pfad-Umbenennungen.

Performance-Ziele:

- Median-Laufzeit < 5s auf Drift-Self-Repo-Diff.
- P95-Laufzeit < 10s auf synthetischen Large-Diffs.

Referenzierte Artefakte:

- Tests: `tests/test_blast_radius_*.py`, `tests/fixtures/blast_radius/`
- Audit-Pflichtupdates: `audit_results/fmea_matrix.md`,
  `audit_results/risk_register.md`, `audit_results/fault_trees.md`,
  `audit_results/stride_threat_model.md`
- Feature-Evidence: `benchmark_results/v<version>_blast_radius_feature_evidence.json`
- Schema: `src/drift/blast_radius/_models.py`

Erwartetes Lernzyklus-Ergebnis (Policy §10): **unklar** bis nach 30 Tagen
Field-Use. Bestätigt wird die Entscheidung, wenn:

- ≥ 1 kritische ADR-Invalidierung durch Gate blockiert wurde,
- kein False-Positive-Block ohne Ack-Rechtfertigung aufgetreten ist,
- Median-Laufzeit über 7 Tage < 5s bleibt.

Widerlegt, wenn Maintainer > 20% aller Blast-Reports mit Bypass-Env umgehen
(Signal: Gate ist zu breit kalibriert).

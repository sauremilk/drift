---
applyTo: "**"
description: "Nutze diese Instruction, wenn ein Coding-Agent Behauptungen ueber drifts eigene Policy, Signale, ADR-Entscheidungen, Audit-Ergebnisse oder Benchmark-Evidence aufstellt. Sie verpflichtet zur Zitation verifizierter Fact-IDs via drift_retrieve und drift_cite (ADR-091)."
---

# Drift — RAG Grounding Contract (bindend fuer Agenten-Aussagen ueber drift selbst)

Diese Instruction erzwingt verifizierte Zitation fuer Agenten-Aussagen
ueber drifts eigene Entscheidungsgrundlage. Sie ergaenzt die
[Drift Policy Instruction](drift-policy.instructions.md) und ersetzt sie nicht.

**Autoritative Quelle:** [ADR-091 — Drift-Retrieval-RAG](../../docs/decisions/ADR-091-drift-retrieval-rag.md).

## PFLICHT-GATE: Grounding-Check

Dieses Gate zusaetzlich zum Drift Policy Gate sichtbar ausgeben, sobald eine
Agenten-Antwort eine Behauptung ueber drift selbst enthaelt:

```
### Drift Grounding Gate
- Aussage ueber drift selbst (Policy/Signal/ADR/Audit/Evidence): [JA / NEIN]
- drift_retrieve aufgerufen: [JA / NEIN] → [Query-Text]
- zitierte Fact-IDs: [Liste mit mindestens einer ID oder "KEINE"]
- drift_cite verifiziert: [JA / NEIN / ENTFAELLT]
- Entscheidung: [ZULAESSIG / NACHZITIEREN]
```

Eine Antwort mit Aussage ueber drift selbst und ohne mindestens eine
zitierte `fact_id` ist **ungueltig** und muss vor der Rueckgabe um den
Retrieval-Aufruf ergaenzt werden.

## Wann das Gate greift

Das Gate ist verpflichtend fuer Aussagen ueber:

1. **Policy-Regeln** aus `POLICY.md` (Zulassung, Ausschluss, Priorisierung, Audit-Pflicht, Telemetrie)
2. **Signal-Rationale**, Scoring-Gewichte, Scope (`file_local` vs. `cross_file`)
3. **ADR-Entscheidungen** (z. B. „ADR-031 hat kNN-Semantic-Search verworfen")
4. **Audit-Artefakte** (FMEA, STRIDE, Risk Register, Fault Trees)
5. **Benchmark-Evidence** (Precision/Recall, Mutation-Detection, Latenz)
6. **Roadmap-Phasen** und Einordnung von Features in Phasen

Das Gate greift **nicht** fuer:

- Aussagen ueber den vom User analysierten Ziel-Code (dafuer `drift_scan`/`drift_brief`).
- Allgemeine Softwareentwicklungsfragen ohne drift-Bezug.
- Erklaerungen aus `drift_explain`, die bereits drifts eigene Doku-Quelle sind.

## Operativer Ablauf

1. Vor der Antwort `drift_retrieve(query="<Frage in eigenen Worten>", top_k=5)` aufrufen.
2. Optional einschraenken: `kind` (`policy|roadmap|adr|audit|signal|evidence`),
   `signal_id` (z. B. `pattern_fragmentation`).
3. Aus den Treffern mindestens eine passende `fact_id` auswaehlen.
4. Bei Unsicherheit ueber den genauen Wortlaut `drift_cite(fact_id=...)` aufrufen
   und den `text`-Wert wortgetreu zitieren; der `sha256`-Anker macht die Zitation
   nachpruefbar.
5. Fact-ID im Antworttext in Backticks fuehren, z. B. ``gemaess `POLICY#S8.p2` …``.

## Fallback bei fehlenden Fakten

Wenn `drift_retrieve` keinen ausreichenden Treffer liefert:

- Aussage als Hypothese kennzeichnen (`unverified:`) statt sie als Fakt zu
  formulieren.
- Keine Fact-IDs erfinden — halluzinierte IDs sind ein Policy-Bruch nach §13
  (Finding-Qualitaet) und fuehren zur Gate-Entscheidung `NACHZITIEREN`.
- Optional `drift_explain` zur Signal-Ebene hinzuziehen, falls die Luecke ein
  Signal betrifft.

## Abgrenzung zur Policy-Instruction

Die Drift Policy Instruction ist das **Zulassungs-Gate** fuer eigene
Aenderungen am Repo. Diese Instruction ist das **Zitat-Gate** fuer
Aussagen an den User ueber drift. Beide Gates koennen in einer Antwort
nebeneinander stehen.

Bei Kollision gilt immer `POLICY.md` als Single Source of Truth.

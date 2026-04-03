---
name: "Drift Context Eval"
agent: agent
description: "Kontext-Qualitaet: Sind Drift-Exporte fuer dieses Repo nuetzlich? Token-Budget, Relevanz, Rauschen, Actionability, Stabilitaet."
---

# Drift Context Eval

Du bewertest, ob die von Drift exportierten Kontexte für ein beliebiges Repository nützlich, präzise und effizient genug für AI-Workflows sind.

> **Pflicht:** Vor Ausführung dieses Prompts das Drift Policy Gate durchlaufen:

### Drift Policy Gate (vor Ausführung ausfüllen)

```
- Aufgabe: [Kurzbeschreibung]
- Zulassungskriterium erfüllt: [JA / NEIN] → [Unsicherheit / Signal / Glaubwürdigkeit / Handlungsfähigkeit / Trend / Einführbarkeit]
- Ausschlusskriterium ausgelöst: [JA / NEIN] → [falls JA: welches]
- Entscheidung: [ZULÄSSIG / ABBRUCH]
- Begründung: [ein Satz]
```

Bei ABBRUCH: keine Ausführung des Prompts.

> **Voraussetzung:** `drift-field-test.prompt.md` sollte vorher gelaufen sein und `pass` ergeben haben.

## Verwandte Prompts

- `drift-field-test.prompt.md` (Voraussetzung)
- `drift-finding-audit.prompt.md` (Signal-Korrektheit)

## Scope

- **Testet:** Ob Drift-Exporte für einen Agent nützlich sind, der DIESES Repo nicht kennt
- **Testet NICHT:** Ob die Findings korrekt sind (→ `drift-finding-audit`)
- **Issues gehen an:** `mick-gsk/drift` — nicht ans Ziel-Repo

## Arbeitsmodus

- Bewerte Outputs aus LLM-Consumer-Perspektive: Token-Kosten vs. Informationsgewinn.
- Vergleiche Formate Seite an Seite statt isoliert zu bewerten.
- Trenne generischen Inhalt (auf jedes Repo zutreffend) von repo-spezifischem Inhalt.
- Sage explizit, ob fehlende Struktur Automation blockiert oder nur Qualität senkt.
- Messe Rauschen als Anteil der Tokens, die keinen repo-spezifischen Wert liefern.

## Ziel

Bestimme, ob die Drift-Exports für dieses Repository genug repo-spezifische, actionable Informationen liefern, um Token-Kosten zu rechtfertigen — und welches Format für welchen Use-Case am besten passt.

## Erfolgskriterien

Die Aufgabe ist erst abgeschlossen, wenn du beantworten kannst:
- Welches Export-Format ist für dieses Repo am nützlichsten?
- Wie hoch ist der Anteil generischer vs. repo-spezifischer Inhalte?
- Passen die Exports in realistische Token-Budgets (8k / 32k)?
- Sind die Exports über wiederholte Läufe stabil?
- Kann ein Agent basierend auf dem Kontext sinnvoll handeln?

## Bewertungs-Labels

Verwende ausschließlich diese Labels:

- **Ergebnis-Bewertung:** `pass` / `review` / `fail`
- **Risiko-Level:** `low` / `medium` / `high` / `critical`
- **Idempotenz:** `stable` / `ordering-unstable` / `content-unstable`

## Artefakte

Erstelle Artefakte unter `work_artifacts/context_eval_<YYYY-MM-DD>/`:

1. `repo_profile.md`
2. `export_instructions.md`
3. `export_prompt.md`
4. `export_raw.json`
5. `copilot_context.md`
6. `context_eval_report.md`

## Workflow

### Phase 0: Repo-Profil erstellen

**Versions-Freshness sicherstellen:**

```bash
pip install --upgrade drift-analyzer   # Aktuellste Version von PyPI
drift --version                        # Version dokumentieren
```

Falls das Upgrade scheitert (Netzwerk, Index), dies im Report dokumentieren
und mit der aktuell installierten Version fortfahren.

**Identisches Profil wie in `drift-finding-audit` Phase 0:**

| Eigenschaft | Wert |
|-------------|------|
| Repository | [OWNER/NAME] |
| Architektur-Typ | [Monolith / Microservice / Library / Framework / Monorepo] |
| Sprache(n) | [Python / TypeScript / Mixed] |
| Framework(s) | [Django / Flask / FastAPI / Express / None / ...] |
| Ungefähre Größe | [Dateien / LOC] |
| drift-Version | [VERSION] |

### Phase 1: Alle Export-Formate ausführen

```bash
drift export-context --repo . --format instructions -o export_instructions.md
drift export-context --repo . --format prompt -o export_prompt.md
drift export-context --repo . --format raw -o export_raw.json
drift copilot-context --repo . > copilot_context.md
```

Alle 4 Outputs in die Artefakte speichern.

### Phase 2: Token-Budget-Check

Für jedes Format Token-Kosten schätzen:

```bash
python -c "import pathlib; txt = pathlib.Path('<DATEI>').read_text(encoding='utf-8'); words = len(txt.split()); print(f'words={words}, tokens_est={int(words*1.35)}')"
```

> **Hinweis:** `words × 1.35` ist eine Heuristik. Für präzise Messung den Tokenizer des Ziel-LLMs verwenden.

| Format | Wörter (ca.) | Tokens (ca.) | Passt in 8k? | Passt in 32k? | Budget-Risiko |
|--------|-------------|-------------|-------------|--------------|---------------|
| instructions | | | | | `low` / `medium` / `high` |
| prompt | | | | | |
| raw | | | | | |
| copilot-ctx | | | | | |

> **Budget-Risiko:** `low` = < 4k tokens, `medium` = 4-16k, `high` = > 16k

### Phase 3: Relevanz-Check

Für jedes Format den Inhalt auf Repo-Spezifizität prüfen:

**Methode:** Lies den Export und klassifiziere jeden inhaltlichen Block:

| Block/Regel/Abschnitt | Generisch? | Repo-spezifisch? | Actionable? |
|------------------------|-----------|-------------------|-------------|
| [Beispiel: "Avoid circular imports"] | Ja | Nein | Bedingt |
| [Beispiel: "Module X has high coupling to Y"] | Nein | Ja | Ja |

**Zusammenfassung pro Format:**

| Format | Generische Blöcke | Repo-spezifische Blöcke | Spezifizitäts-Anteil |
|--------|-------------------|-------------------------|---------------------|
| instructions | | | [%] |
| prompt | | | [%] |
| raw | | | [%] |
| copilot-ctx | | | [%] |

> **Bewertung:** Spezifizitäts-Anteil < 30% = `fail` (zu generisch), 30-60% = `review`, > 60% = `pass`

### Phase 4: Rausch-Check

Signal-zu-Rausch-Verhältnis berechnen:

| Format | Gesamt-Tokens (ca.) | Repo-spezifische Tokens (ca.) | Tokens pro actionable Insight | Effizienz |
|--------|---------------------|-------------------------------|-------------------------------|-----------|
| instructions | | | | `high` / `medium` / `low` |
| prompt | | | | |
| raw | | | | |
| copilot-ctx | | | | |

**Rausch-Quellen identifizieren:**
- Wiederholte generische Warnungen
- Boilerplate-Text ohne Informationsgehalt
- Redundanz zwischen Abschnitten
- Formatierungs-Overhead (Markdown-Syntax, JSON-Struktur)

### Phase 5: Actionability

Für jedes Format bewerten, ob ein Agent damit handeln kann:

| Kriterium | instructions | prompt | raw | copilot-ctx |
|-----------|-------------|--------|-----|-------------|
| Identifiziert konkrete Dateien/Module? | | | | |
| Benennt spezifische Risiken? | | | | |
| Schlägt nächsten Schritt vor? | | | | |
| Maschinenlesbar (parsbar ohne NLP)? | | | | |
| Agent-tauglich (Score 1-2)? | | | | |

**Actionability-Score pro Format:** `1 automated` / `2 guided` / `3 human-review` / `4 blocked`

### Phase 6: Stabilitäts-Check

Jeden Export-Befehl zweimal ausführen und diffen:

```bash
drift export-context --repo . --format instructions -o run1_instructions.md
drift export-context --repo . --format instructions -o run2_instructions.md
diff run1_instructions.md run2_instructions.md

drift export-context --repo . --format raw -o run1_raw.json
drift export-context --repo . --format raw -o run2_raw.json
diff run1_raw.json run2_raw.json
```

| Format | Diff vorhanden? | Klassifikation |
|--------|----------------|----------------|
| instructions | | `stable` / `ordering-unstable` / `content-unstable` |
| prompt | | |
| raw | | |
| copilot-ctx | | |

### Phase 7: Report erstellen

```markdown
# Drift Context Eval Report

**Datum:** <YYYY-MM-DD>
**drift-Version:** [VERSION]
**Repository:** [OWNER/REPO-NAME]
**Repo-Typ:** [Architektur-Typ + Framework]

## Repo-Profil

[Tabelle aus Phase 0]

## Format-Vergleich

| Format | Tokens (ca.) | Spezifizität | Effizienz | Actionability | Stabilität | Gesamt |
|--------|-------------|-------------|-----------|---------------|-----------|--------|
| instructions | | | | | | `pass`/`review`/`fail` |
| prompt | | | | | | |
| raw | | | | | | |
| copilot-ctx | | | | | | |

## Token-Budget-Risiko

[Tabelle aus Phase 2]

## Rausch-Quellen

[Top-3-Rauschquellen mit Token-Impact]

1. [...]
2. [...]
3. [...]

## Format-Empfehlung

| Use Case | Empfohlenes Format | Begründung |
|----------|--------------------|------------|
| System-Prompt in Coding Agent | | |
| CI-Pipeline-Annotation | | |
| MCP-Tool-Integration | | |
| Human Code Review | | |
| Automated Orchestration | | |

## Gesamtbewertung

- Kontext-Qualität für dieses Repo: [pass / review / fail]
- Bestes Format: [NAME] — weil [BEGRÜNDUNG]
- Größtes Problem: [BESCHREIBUNG]
- Empfohlener nächster Schritt: [Issues melden / keine Aktion]

## Prioritäre Verbesserungen für drift

1. [...]
2. [...]
3. [...]
```

## Entscheidungsregel

Wenn ein Format informativ aussieht, aber hauptsächlich generischen Inhalt liefert: nicht hoch bewerten. Token-Kosten müssen durch repo-spezifischen Wert gerechtfertigt sein.

## GitHub-Issue-Erstellung

Am Ende des Workflows GitHub-Issues auf `mick-gsk/drift` erstellen (nicht das analysierte Ziel-Repo).

**Sprache:** Englisch (Titel + Body + Kommentare).

**Issue-Regeln:**
1. Vor Erstellung prüfen, ob ein passendes Issue auf `mick-gsk/drift` bereits existiert
2. Ein Issue pro Problem — keine Sammel-Issues
3. Evidenz-Pflicht — Kommando, drift-Version, Repo-Infos angeben
4. Nur reproduzierbare Defekte — kein lokales Umgebungsrauschen
5. Labels: `field-test` plus ggf. `agent-ux`, `signal-quality`, `bug`

**Titel-Format:** `[field-test:context-eval] <concise problem description> (tested on <repo-name>)`

**Body-Template (English):**

```markdown
## Observed behavior
[What drift produced — include relevant output snippet]

## Expected behavior
[What would have been correct/useful for this repository type]

## Tested repository
- **Repository:** [OWNER/REPO-NAME]
- **Commit:** [COMMIT-HASH or branch]
- **Repo type:** [Python / TypeScript / Mixed]
- **Repo profile:** [Library / Framework / Application / Monorepo]
- **drift version:** [VERSION]
- **Command:** `drift ...`

## Impact
- [ ] Context quality issue (too generic / too noisy / unstable / incomplete)

## Generalizability estimate
[Is this specific to this repo or would it affect similar repos?]

## Source
Auto-generated by `drift-context-eval.prompt.md` on [DATE].
Tested on [OWNER/REPO-NAME] at commit [SHORT-HASH].
```

**Prompt-Kürzel für Titel:** `context-eval`

### Issues erstellen für

- Export-Formate mit Spezifizitäts-Anteil < 30% (zu generisch für praktischen Nutzen)
- Content-Instabilität (unterschiedliche Ergebnisse ohne Repo-Änderung)
- Token-Budget-Überschreitung > 32k bei normalgroßem Repo (< 5000 Dateien)
- Fehlende repo-spezifische Informationen, die in der `analyze`-Ausgabe vorhanden waren
- Maschinenlesbarkeits-Probleme im `raw`-Format (unparsbare Struktur)

### Keine Issues erstellen für

- Subjektive Formatpräferenzen
- Generischer Inhalt, der dennoch korrekt ist (nur wenn Token-ineffizient)
- Ordering-Instabilität (dokumentieren, aber kein Issue, wenn Inhalt identisch)
- Repo-spezifische Kontext-Lücken, die drift nicht kennen kann

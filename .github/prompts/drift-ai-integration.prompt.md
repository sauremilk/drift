---
name: "Drift AI Integration"
agent: agent
description: "Evaluiert, ob Drift-Outputs für LLMs und Agent-Frameworks tatsächlich nützlich sind: Context-Exporte vergleichen, MCP-Readiness testen, Prompt-Qualität und Signal-Dichte bewerten."
---

# Drift AI Integration

Du evaluierst Drift als Kontext-Generierungs- und Tool-Integrationsschicht für LLMs und Coding-Agents.

> **Pflicht:** Vor Ausführung dieses Prompts das Drift Policy Gate durchlaufen
> (siehe `.github/prompts/_partials/konventionen.md` und `.github/instructions/drift-policy.instructions.md`).

## Relevante Referenzen

- **Instruction:** `.github/instructions/drift-policy.instructions.md`
- **Bewertungssystem:** `.github/prompts/_partials/bewertungs-taxonomie.md`
- **Issue-Filing:** `.github/prompts/_partials/issue-filing.md`
- **Verwandte Prompts:** `drift-agent-workflow-test.prompt.md` (Phase 7c testet copilot-context/export-context)
- **ADR:** `.internal/docs/decisions/ADR-002-export-context-format-semantics.md` (Format-Semantik-Entscheidung)
- **Implementierung:** `src/drift/negative_context_export.py` (Export-Logik)

## Arbeitsmodus

- Bewerte jeden AI-facing Output auf Token-Effizienz UND semantischen Nutzen.
- Vergleiche Formate Seite an Seite und erkläre Tradeoffs statt sie isoliert zu scoren.
- Trenne menschliche Lesbarkeit von Agent-Nützlichkeit, wenn diese divergieren.
- Sage explizit, ob fehlende Struktur Automation blockiert oder nur Qualität senkt.
- Fasse Kontext-Defekte in Begriffen zusammen, was ein LLM als nächstes falsch machen würde.

## Ziel

Bestimme, ob Drift AI-facing Outputs produziert, die prägnant, treu und operationell nützlich für Prompt-Injection, Agent-Planung und MCP-basierte Tool-Nutzung sind.

## Erfolgskriterien

Die Aufgabe ist erst abgeschlossen, wenn du beantworten kannst:
- Welche exportierten Kontextformate sind am nützlichsten für AI-Workflows?
- Ist der generierte Kontext präzise genug, damit ein Agent handeln kann?
- Sind MCP-Startup und -Nutzung verständlich und testbar?
- Welche AI-facing Outputs sind redundant, verrauscht oder fehlt Schlüsselstruktur?
- Passt jedes Format in realistische LLM-Kontextbudgets (8k / 32k Tokens)?
- Ist der Output über wiederholte Läufe auf gleichem Repo-State stabil?
- Ist die Format-Struktur maschinenlesbar (parsbar ohne NLP)?
- Welches Format ist für welchen konkreten Integrationsfall empfohlen?

## Arbeitsregeln

- Bewerte Outputs aus LLM-Consumer-Perspektive, nicht nur Mensch-Perspektive.
- Bestraft Redundanz, wenn sie Tokens kostet ohne Actionability zu verbessern.
- Bevorzuge Side-by-Side-Vergleiche, wenn mehrere Formate die gleiche Information zeigen.
- Sage explizit, ob ein Format besser für Menschen, Prompts oder Machine-Orchestration ist.
- Wenn ein MCP-Pfad nicht vollständig testbar ist, dokumentiere die tiefste realistische Testgrenze.

## Bewertungs-Labels

Verwende ausschließlich Labels aus `.github/prompts/_partials/bewertungs-taxonomie.md`:

- **Ergebnis-Bewertung** pro Format/Test: `pass` / `review` / `fail`
- **Risiko-Level**: `low` / `medium` / `high` / `critical`

## Artefakte

Erstelle Artefakte unter `work_artifacts/ai_integration_<YYYY-MM-DD>/`:

1. `copilot_context_preview.md`
2. `export_instructions.md`
3. `export_prompt.md`
4. `export_raw.md`
5. `mcp_notes.md`
6. `ai_integration_report.md`

## Workflow

### Phase 0: AI-facing Oberflächen inventarisieren

**Dev-Version sicherstellen** (siehe `_partials/konventionen.md` → Versions-Freshness):

```bash
pip install -e .   # Dev-Version aus Workspace
drift --version    # Muss mit pyproject.toml übereinstimmen
```

Identifiziere alle derzeit exponierten AI-facing Features:
- `copilot-context`
- `export-context` (Formate: `instructions`, `prompt`, `raw`)
- `mcp`

Dokumentiere, was jede Oberfläche beabsichtigt, bevor du Qualität bewertest.

**Format-Semantik (gemäß ADR-002):**
- `instructions` — Ausführliches Markdown für System-Prompts
- `prompt` — Kompakte einzeilige DO_NOT→INSTEAD-Regeln
- `raw` — Maschinenlesbares JSON (Schema: `drift-negative-context-v1`)

### Phase 1: Exportierte Kontextformate vergleichen

Teste sowohl Preview- als auch File-Outputs:

```bash
drift copilot-context --repo .
drift export-context --repo . --format instructions
drift export-context --repo . --format prompt
drift export-context --repo . --format raw
```

Für jedes Format bewerten:
- Klarheit
- Redundanz
- Actionability
- Kompatibilität mit Agent-Workflows

### Token-Budget-Check

Für jedes Format Token-Kosten schätzen:

```bash
python -c "import pathlib; txt = pathlib.Path('<DATEI>').read_text(); words = len(txt.split()); print(f'words={words}, tokens_est={int(words*1.35)}')"
```

> **Hinweis:** Die Formel `words × 1.35` ist eine Heuristik. Für präzise Messungen `tiktoken` (OpenAI) oder den Tokenizer des Ziel-LLMs verwenden. Für diese Evaluation reicht die Heuristik als Größenordnungsschätzung.

| Format | Wörter (ca.) | Tokens (ca.) | Passt in 8k? | Passt in 32k? | Als Single-File-Agent-Kontext nutzbar? |
|--------|-------------|-------------|-------------|--------------|---------------------------------------|
| instructions | | | | | |
| prompt | | | | | |
| raw | | | | | |
| copilot-ctx | | | | | |

Wenn ein Format bei typischer Repo-Größe 32k Tokens überschreitet: als **context-budget-risk** flaggen.
Token-Budget-Schwelle ist konfigurierbar; Default 32k entspricht konservativer Schätzung für Modelle mit 128k-Kontext, die noch Platz für Aufgabe + Code brauchen.

### Stabilitäts-Check

**Beide** Oberflächen jeweils zweimal ohne Repo-Änderungen ausführen und diffen:

```bash
drift export-context --repo . --format instructions -o run1_instructions.md
drift export-context --repo . --format instructions -o run2_instructions.md
diff run1_instructions.md run2_instructions.md

drift copilot-context --repo . > run1_copilot.md
drift copilot-context --repo . > run2_copilot.md
diff run1_copilot.md run2_copilot.md
```

Klassifikation pro Format:
- `stable`: kein Diff oder nur Metadaten (Timestamp, Version)
- `format-unstable`: gleicher Inhalt, andere Reihenfolge/Formatierung — schlecht für Caching
- `content-unstable`: Inhalt differiert ohne Repo-Änderung — Bug

### Struktur-Check

Pro Format Maschinen-Parsbarkeit bewerten:
- Gibt es stabile Sections (Headings, Keys) die programmatisch extrahierbar sind?
- Sind Signal-Bezeichner konsistent mit CLI-Output (gleiche Abkürzungen, IDs)?
- Kann ein Automations-Tool einzelne Regeln/Constraints ohne NLP isolieren?

Klassifikation:
- `unstructured`: Nur Freitext, nicht parsbar
- `semi-structured`: Listen/Sections, aber keine stabilen Keys
- `structured`: Klar parsbare Blöcke mit stabilen IDs/Keys

### Phase 2: Nützlichkeit als Agent-Kontext testen

Bewerte, ob der exportierte Inhalt einem LLM hilft:
- Repository-Zustand schnell verstehen
- Wahrscheinliche Architekturrisiken identifizieren
- Sinnvolles nächstes Kommando oder Fix-Pfad wählen
- Kontext-Fenster nicht mit low-value Wiederholung verschwenden

### Phase 2b: End-to-End-Inject-Test

Dies ist der einzige Test, der empirisch belegt, ob `export-context` Modellverhalten verbessert.

Bereite eine minimale Oracle-Datei mit 2–3 bekannten Drift-Violations vor (aus existierenden Benchmark-Fixtures oder kleinem synthetischen Beispiel). Dann zwei Varianten ausführen:

**Variante A — ohne Drift-Kontext:**
Nur Oracle-Code dem Modell übergeben. Frage: „Welche Architektur-Probleme siehst du in diesem Code?"

**Variante B — mit Drift-Kontext:**
Best-scoring Export-Format als System-Prompt injizieren. Identische Frage stellen.

| Metrik | Ohne Kontext | Mit Kontext | Delta |
|--------|-------------|------------|-------|
| Violations erkannt | | | |
| Violations übersehen | | | |
| Halluzinationen | | | |
| Token-Kosten der Injection | n/a | | |

> **Hinweis:** Dieser Test erfordert manuelle oder LLM-gestützte Bewertung. Falls eine automatisierte Auswertung nicht möglich ist, Ergebnisse als qualitativ kennzeichnen.

Schlussfolgerung: Rechtfertigen die Token-Kosten den Qualitätsgewinn?

### Phase 3: MCP-Readiness testen

Beide Pfade prüfen:

```bash
drift mcp
drift mcp --serve
```

Bewerte:
- Auffindbarkeit der Voraussetzungen
- Klarheit beim Startup
- Klarheit bei Fehler (wenn optionale Dependencies fehlen)
- Praktische Nutzbarkeit für einen realen Agent-Client

### MCP-Client-Perspektive

Tool-Definitionen des MCP-Servers extrahieren (via Startup-Output, JSON-Schema oder Dokumentation). Für jedes Tool:
- Ist der Name aus LLM-Perspektive selbsterklärend?
- Ist die Beschreibung ausreichend, um das Tool korrekt aufzurufen?
- Sind Parameter klar typisiert mit sinnvollen Defaults?

MCP-Readiness-Klassifikation:
- `mcp-ready`: Direkt nutzbar in Standard-MCP-Client ohne Extra-Doku
- `mcp-fragile`: Funktional, aber nur mit handgeschriebener Ergänzung
- `mcp-unusable`: Fehlende oder irreführende Tool-Metadaten verhindern zuverlässige Nutzung

### Phase 4: Report erstellen

```markdown
# Drift AI Integration Report

**Datum:** <YYYY-MM-DD>
**drift-Version:** [VERSION]
**Repository:** [REPO-NAME]

## Format-Vergleich

| Oberfläche | Bestes für | Stärken | Schwächen | Bewertung |
|------------|-----------|---------|-----------|-----------|

## Kontext-Qualität

| Kriterium | instructions | prompt | raw | copilot-ctx | Anmerkungen |
|-----------|-------------|--------|-----|-------------|-------------|
| Klarheit | | | | | |
| Actionability | | | | | |
| Redundanz | | | | | |
| Agent-Nützlichkeit | | | | | |
| Token-Effizienz | | | | | |

## MCP-Readiness

| Pfad | Testtiefe | Ergebnis | Agent-Nutzbarkeit | Anmerkungen |
|------|-----------|----------|-------------------|-------------|

## Prioritäre Verbesserungen

1. [...]
2. [...]
3. [...]

## Empfohlene Integrationspfade

| Use Case | Empfohlenes Format | Begründung |
|----------|--------------------|------------|
| System-Prompt in Coding Agent | | |
| GitHub Actions Annotation | | |
| MCP Tool Integration | | |
| Human Code Review Prep | | |
| Automated Orchestration Pipeline | | |
```

## Entscheidungsregel

Wenn ein Format informativ aussieht, aber Tokens verschwendet oder den Agent nicht sinnvoll lenkt: nicht hoch bewerten.

## GitHub-Issue-Erstellung

Am Ende des Workflows GitHub-Issues erstellen gemäß `.github/prompts/_partials/issue-filing.md`.

**Prompt-Kürzel für Titel:** `ai-integration`

### Issues erstellen für

- Exportierter Kontext, der zu verrauscht, unvollständig oder irreführend für Agent-Nutzung ist
- Wesentliche Inkonsistenzen zwischen `instructions`, `prompt` und `raw`
- MCP-Startup- oder Nutzungsprobleme durch Drift-Verhalten oder fehlende Anleitung
- Fehlende Struktur, die praktische Nutzung in Prompts oder Tooling verhindert

### Keine Issues erstellen für

- Rein subjektive Formatpräferenzen ohne Workflow-Impact
- Lokale Client-Einschränkungen außerhalb von Drifts Verantwortung
- Duplikate bereits existierender Issues

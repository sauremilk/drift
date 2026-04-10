# Diagnose vs. Navigation

Drift hat zwei konzeptionell verschiedene Betriebs­modi: **Diagnose** und **Navigation**. Dieser Unterschied ist zentral für die Frage, wann welcher Befehl eingesetzt werden sollte.

---

## Zwei Fragen — zwei Modi

| Frage | Modus | Befehle |
|-------|-------|---------|
| „Wie gesund ist mein Repository?" | **Diagnose** | `drift analyze`, `drift scan`, `drift check` |
| „Bewegen sich meine Änderungen in die richtige Richtung?" | **Navigation** | `drift nudge`, `drift brief` |

Diagnose ist synchron und vollständig: Alle aktiven Signals werden auf dem gesamten Repository ausgewertet, ein Composite-Score wird berechnet, alle Findings werden priorisiert zurückgegeben.

Navigation ist inkrementell und direktional: Nur die geänderten Dateien werden mit exakter Konfidenz analysiert; cross-file-abhängige Signals werden aus einem In-Memory-Baseline-Snapshot fortgetragen. Das Ergebnis ist kein vollständiger Report — es ist ein Richtungssignal: `"improving"`, `"stable"` oder `"degrading"`.

---

## Diagnose-Modus

### Wann einsetzen?

- Vor einem Release oder Sprint-Abschluss: Repository-Gesundheit bewerten
- In CI: `drift check` blockiert PRs, die Schwellwerte überschreiten
- Beim erstmaligen Onboarding: Baseline-Stand ermitteln (`drift baseline save`)
- Nach einem größeren Refactoring: Auswirkungen messen

### Wie es funktioniert

`drift scan` und `drift analyze` führen eine **Vollanalyse** durch:

1. Alle Quelldateien werden über den AST-Parser eingelesen (parallel, konfigurierbares Workers-Setting)
2. Git-History der letzten `--since` Tage wird geladen (Commits, File-Histories, AI-Attribution)
3. Alle aktiven Signals werden mit Zugriff auf den vollen Repository-Kontext ausgewertet
4. Signal-Scores werden gewichtet zu einem Composite-Score aggregiert
5. Findings werden priorisiert (Severity + Impact + Breadth) und zurückgegeben

**Ergebnis:** Ein vollständiger, reproduzierbarer Snapshot mit Composite-Score und allen Findings.

```bash
# Diagnose: vollständige Analyse
drift scan --repo . --max-findings 10

# Diagnose in CI: Exit 1 bei high-Findings seit gestern
drift check --diff HEAD~1 --fail-on high
```

### Einschränkung

Vollanalysen dauern bei großen Repositories mehrere Sekunden (manchmal > 10 s), weil AST-Parsing und Git-History-Verarbeitung parallelisiert aber nicht inkrementell sind. Das macht sie ungeeignet als Feedback-Loop während aktiver Entwicklung in kurzen Iterationszyklen.

---

## Navigations-Modus

### Wann einsetzen?

- Während aktiver Entwicklung: Nach jeder Dateiänderung wissen, ob die Änderung die Codebasis verbessert oder verschlechtert
- In KI-Agenten-Loops: KI-Agenten sollen nur dann fortfahren, wenn `safe_to_commit == true`
- Vor einem Commit: Schnelle Sanity-Check ohne vollständige Analyse
- Beim Planen einer KI-generierten Änderung: `drift brief` liefert Guardrails als Prompt-Constraints

### `drift nudge` — Direktionales Feedback

`drift nudge` ist das Kernwerkzeug des Navigations-Modus. Es antwortet auf die Frage: „Hat meine letzte Änderung die architektonische Kohärenz verbessert oder verschlechtert?"

**Wie es funktioniert:**

1. Drift erkennt geänderte Dateien (über `git diff --name-only HEAD`)
2. File-lokale Signals (PFS, MDS, EDS, BEM, TPD, GCD, NBV, BAT) werden nur auf den geänderten Dateien mit **exakter Konfidenz** neu berechnet
3. Cross-file-abhängige Signals (AVS, CCC, SMS etc.) werden aus dem letzten In-Memory-Baseline-Snapshot **fortgetragen** mit dem Vermerk `"estimated"` — sie werden nicht neu berechnet
4. Der inkrement­elle Score wird mit dem Baseline-Score verglichen: `delta = current - baseline`
5. Basierend auf delta > 0.005 (degrading), < −0.005 (improving) oder dazwischen (stable) wird `direction` gesetzt

**Ergebnis:**

```json
// Beispiel-Output
{
  "direction": "improving",
  "delta": -0.04,
  "safe_to_commit": true,
  "new_findings": [],
  "resolved_findings": [
    {
      "signal": "PFS",
      "title": "Error handling fragmented (3 variants)",
      "file": "src/api/handlers.py"
    }
  ],
  "confidence": {
    "pattern_fragmentation": "exact",
    "architecture_violation": "estimated"
  }
}
```

**In der Praxis (MCP-Agenten-Loop):**

```
Bearbeite Datei src/api/handlers.py
  → drift_nudge(changed_files=["src/api/handlers.py"])
  → direction: "improving", safe_to_commit: true
  → Commit vorbereiten
```

**Baseline-Verwaltung:** Der In-Memory-Baseline-Snapshot hat TTL = 15 Minuten. Wenn keine Baseline existiert, führt `nudge` automatisch eine Vollanalyse durch, um eine zu erstellen. Falls die Baseline abgelaufen ist oder sich der Git-State (HEAD, Stash, dirty files) wesentlich geändert hat, wird sie invalidiert und neu erstellt.

### `drift brief` — Pre-Task-Guardrails

`drift brief` antwortet auf die Frage: „Welche strukturellen Constraints muss ich beim Bearbeiten dieser Aufgabe beachten?" Es ist ein Navigations-Werkzeug für den *Moment vor* der Implementierung, nicht danach.

```bash
drift brief --task "add payment integration to checkout module"
drift brief -t "refactor auth service" --format json
drift brief -t "add caching to API layer" --scope src/api/
```

**Wie es funktioniert:**

1. Die Aufgabenbeschreibung wird analysiert, um den relevanten Scope zu bestimmen
2. Aktuelle Findings im betroffenen Bereich werden identifiziert
3. Für jedes relevante Finding wird ein **Guardrail** erzeugt — eine strukturierte Prompt-Constraint, die einem KI-Agenten sagt, welche Muster verboten sind und welche bevorzugt werden sollen
4. Guardrails werden nach Pre-Task-Relevanz sortiert (AVS, PFS, MDS haben höchste Relevanz)

**Ergebnis (Markdown, für Agenten-Prompts):**

```markdown
// Beispiel-Output
## Structural Constraints (generated by drift brief)

CONSTRAINT [PFS]: Keep error handling uniform within src/checkout/.
Do NOT: Mix return-code-based and exception-based error handling.

CONSTRAINT [AVS]: Do not import directly from src/db/ in route handlers.
Do NOT: from db.models import ...  # use service layer instead
```

---

## Wann welchen Modus nutzen — Entscheidungsmatrix

| Situation | Empfehlung |
|-----------|-----------|
| Vor einem Commit prüfen, ob Änderungen sauber sind | `drift nudge` |
| KI-Agenten vor einer Aufgabe mit Constraints briefen | `drift brief --task "..."` |
| PR in CI überprüfen | `drift check --diff main --fail-on high` |
| Repository-Gesundheit einmalig bewerten | `drift scan` |
| Baseline für bestehende Codebase erfassen | `drift baseline save` + `drift check --baseline` |
| Finding-Details verstehen | `drift explain PFS` |
| Signalgewichte projektspezifisch anpassen | `drift calibrate run` |

---

## Vertrauensstufen im Navigations-Modus

`drift nudge` unterscheidet zwei Konfidenz-Level:

| Level | Signal-Typen | Bedeutung |
|-------|-------------|-----------|
| `"exact"` | File-lokale Signals (PFS, MDS, EDS, BEM, TPD, GCD, NBV, BAT) | Vollständig neu berechnet auf den geänderten Dateien |
| `"estimated"` | Cross-file-abhängige Signals (AVS, CCC, SMS, CIR, FOE) | Aus Baseline fortgetragen; können veraltet sein |

Das bedeutet: Wenn eine Änderung `direction: "stable"` zurückgibt, aber AVS-Findings im Scope liegen, ist das AVS-Signal nur geschätzt — eine Vollanalyse (`drift scan`) bleibt die definitive Quelle.

---

## Nächste Schritte

- [**../guides/agent-workflow.md**](../guides/agent-workflow.md) — Navigations-Modus in KI-Agenten-Loops einsetzen (MCP-Server, Nudge-Loop, Fix-Plan)
- [**../guides/ci-integration.md**](../guides/ci-integration.md) — Diagnose-Modus in CI-Pipelines integrieren
- [**scoring.md**](scoring.md) — Wie der Composite-Score im Diagnose-Modus berechnet wird
- [**signals.md**](signals.md) — Welche Signals file-lokal vs. cross-file sind

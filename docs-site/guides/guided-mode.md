# Guided Mode for Vibe-Coders

Drift's **Guided Mode** gives you a simple traffic-light health indicator and copy-paste prompts for your AI assistant — no technical knowledge required.

## Quick start

```bash
pip install drift-analyzer
cd your-project
drift status
```

That's it. You'll see one of three colors:

| Status | Meaning | What to do |
|--------|---------|------------|
| 🟢 GREEN | Your project looks good | Keep building |
| 🟡 YELLOW | Some areas need attention | Copy a prompt and give it to your AI assistant |
| 🔴 RED | Structural problem — fix now | Copy the prompt and fix before continuing |

## How it looks

### GREEN — all clear

```
🟢  Dein Projekt sieht gut aus. Du kannst weiterarbeiten.

Du kannst weiterarbeiten.
```

### YELLOW — needs attention

```
🟡  Es gibt Stellen, die Aufmerksamkeit brauchen.

Top-3 Auffälligkeiten:

  1. Wichtig: Ähnliche Code-Stellen in der Service-Schicht
     Prompt:
     In meinem Projekt gibt es fast identische Code-Abschnitte in
     der Service-Schicht mit kleinen Abweichungen. Bitte fasse
     diese zusammen, sodass die Logik nur einmal existiert.

  2. Auffällig: Fehlerbehandlung zu allgemein in der API-Logik
     ...

Tipp: Kopiere einen der Prompts oben und gib ihn deinem KI-Assistenten.
```

### RED — needs immediate action

```
🔴  Dein Projekt hat ein strukturelles Problem, das du jetzt angehen solltest.

Top-3 Auffälligkeiten:

  1. Kritisch: Die API-Logik greift auf Bereiche zu, die getrennt sein sollten
     Prompt:
     In meinem Projekt greift die API-Logik auf Bereiche zu, die
     eigentlich getrennt sein sollten. Bitte trenne die Zuständig-
     keiten sauber, sodass jede Schicht nur ihre eigene Aufgabe hat.

Tipp: Kopiere einen der Prompts oben und gib ihn deinem KI-Assistenten.
```

## Traffic light thresholds

| Score range | Status | `can_continue` |
|-------------|--------|-----------------|
| < 0.35 | 🟢 GREEN | `true` |
| 0.35 – 0.64 | 🟡 YELLOW | `false` |
| ≥ 0.65 | 🔴 RED | `false` |

**Override rules:**

- Any **critical** finding → RED (regardless of score)
- Any **high** finding → at least YELLOW

## Copy-paste prompts

Drift generates natural-language prompts for each finding — designed to be pasted directly into ChatGPT, Copilot, Cursor, or any AI assistant.

Every prompt follows a three-part structure:

1. **Problem** — what's wrong, in everyday language
2. **Action** — what the AI should do
3. **Expected outcome** — what success looks like

### All 18 prompt templates

| Signal | Prompt (German) |
|--------|----------------|
| PFS (Pattern Fragmentation) | "In meinem Projekt gibt es mehrere Stellen, die dasselbe auf unterschiedliche Art lösen — vor allem in {file_role}. Bitte vereinheitliche diese Stellen..." |
| AVS (Architecture Violation) | "In meinem Projekt greift {file_role} auf Bereiche zu, die eigentlich getrennt sein sollten. Bitte trenne die Zuständigkeiten sauber..." |
| MDS (Mutant Duplicate) | "In meinem Projekt gibt es fast identische Code-Abschnitte in {file_role} mit kleinen Abweichungen. Bitte fasse diese zusammen..." |
| EDS (Explainability Deficit) | "In meinem Projekt ist {file_role} schwer nachvollziehbar. Bitte vereinfache die Logik..." |
| DIA (Doc-Impl Drift) | "Die Dokumentation in meinem Projekt passt nicht mehr zum tatsächlichen Code in {file_role}. Bitte aktualisiere die Dokumentation..." |
| SMS (System Misalignment) | "Die Projektstruktur passt nicht zu dem, was {file_role} tatsächlich tut. Bitte ordne die Dateien so an..." |
| BEM (Broad Exception) | "In {file_role} werden Fehler zu allgemein abgefangen. Bitte verwende spezifischere Fehlerbehandlung..." |
| TPD (Test Polarity) | "Die Tests in meinem Projekt prüfen in {file_role} nur den Normalfall. Bitte ergänze Tests für Fehlerfälle..." |
| GCD (Guard Clause) | "In {file_role} werden Eingaben nicht früh genug geprüft. Bitte füge Prüfungen hinzu..." |
| NBV (Naming Violation) | "In meinem Projekt sind Benennungen in {file_role} inkonsistent. Bitte vereinheitliche die Namensgebung..." |
| BAT (Bypass Accumulation) | "In {file_role} gibt es viele Stellen, an denen Qualitätsprüfungen übersprungen werden. Bitte löse die Probleme..." |
| ECM (Exception Contract) | "Verschiedene Stellen in {file_role} werfen unterschiedliche Fehlertypen für ähnliche Situationen. Bitte vereinheitliche..." |
| COD (Cohesion Deficit) | "In meinem Projekt macht {file_role} zu viele verschiedene Dinge. Bitte teile die Verantwortlichkeiten auf..." |
| CCC (Co-Change Coupling) | "Bestimmte Dateien rund um {file_role} müssen immer zusammen geändert werden. Bitte entkopple diese Abhängigkeiten..." |
| FOE (Fan-Out Explosion) | "In meinem Projekt importiert {file_role} zu viele andere Module. Bitte reduziere die Abhängigkeiten..." |
| HSC (Hardcoded Secret) | "Es gibt fest eingebaute Zugangsdaten in {file_role}. Bitte verschiebe diese in Umgebungsvariablen..." |
| PHR (Phantom Reference) | "In meinem Projekt verweist {file_role} auf Funktionen, die nicht mehr existieren. Bitte entferne oder aktualisiere..." |
| TVS (Temporal Volatility) | "Bestimmte Dateien rund um {file_role} werden ungewöhnlich häufig geändert. Bitte prüfe, ob diese zu viele Aufgaben übernehmen..." |

The `{file_role}` placeholder is automatically replaced with a human-readable description of the affected area (e.g., "die API-Logik", "die Service-Schicht", "die Funktion ‚process_order'").

## File-role detection

Drift maps file paths to **human-readable roles** so prompts never show raw file paths. Detection priority:

1. **AST analysis** — if available: "die Methode ‚process' in der Klasse ‚OrderService'"
2. **Directory heuristic** — maps 30+ common directory names:

| Directory | Role | Directory | Role |
|-----------|------|-----------|------|
| `api`, `routes` | "die API-Logik" | `models`, `schemas` | "die Datenmodelle" |
| `auth`, `login` | "die Authentifizierung" | `services` | "die Service-Schicht" |
| `db`, `database` | "die Datenbankschicht" | `utils`, `helpers` | "die Hilfsfunktionen" |
| `tests`, `test` | "die Tests" | `middleware` | "die Middleware" |
| `handlers` | "die Handler-Logik" | `commands`, `cli` | "die Kommandozeile" |
| `templates` | "die Vorlagen" | `frontend` | "das Frontend" |
| `components` | "die Komponenten" | `pages` | "die Seiten" |
| `plugins` | "die Plugins" | `migrations` | "die Datenbankmigrationen" |

3. **Symbol name** — "den Bereich um ‚process_order'"
4. **Fallback** — "einen Bereich deines Projekts"

## JSON output

For automation, use `drift status --json`:

```json
{
  "status": "yellow",
  "headline": "Es gibt Stellen, die Aufmerksamkeit brauchen.",
  "can_continue": false,
  "calibrated": true,
  "findings_count": 7,
  "top_findings": [
    {
      "signal": "MDS",
      "severity_label": "Wichtig",
      "plain_text": "Ähnliche Code-Stellen in der Service-Schicht",
      "file_role": "die Service-Schicht",
      "file": "src/services/order.py",
      "line": 42,
      "agent_prompt": "In meinem Projekt gibt es fast identische...",
      "fingerprint": "abc123",
      "rank": 1
    }
  ]
}
```

## Profiles

Guided mode uses the **vibe-coding** profile by default — optimized for AI-generated codebases:

| Profile | Purpose | Traffic light | `fail_on` |
|---------|---------|---------------|-----------|
| `vibe-coding` ⭐ | AI-accelerated codebases | ✅ GREEN <0.35 / YELLOW <0.65 / RED ≥0.65 | `none` |
| `default` | Balanced for most projects | ❌ Not set | `none` |
| `strict` | Maximum enforcement | ❌ Not set | `medium` |

The vibe-coding profile upweights signals most relevant for AI-generated code:

- **Mutant duplicates** (0.20) — copy-paste from AI is the #1 concern
- **Bypass accumulation** (0.06) — AI tends to add `# type: ignore`, TODO, FIXME
- **Test polarity** (0.06) — AI tests often only cover happy paths

Switch profiles with:

```bash
drift status --profile strict
drift status --profile default
```

## Setup

For first-time guided onboarding:

```bash
drift setup
```

This asks 3 questions and generates a `drift.yaml` with sensible defaults.

## Severity labels

Guided mode uses everyday German labels instead of technical severity names:

| Technical | Guided Label |
|-----------|-------------|
| `critical` | Kritisch |
| `high` | Wichtig |
| `medium` | Auffällig |
| `low` | Hinweis |
| `info` | Info |

## Integration with `drift analyze`

`drift status` is the simplified entry point. For full analysis:

```bash
drift analyze --repo .          # Full technical output
drift status                    # Traffic light + prompts
```

Both run the same analysis engine — `drift status` just presents results in guided format.

# Product Requirements Document
## drift Guided Mode — v3.0.0

| | |
|---|---|
| **Status** | Draft — Pending Approval |
| **Version** | 1.1 |
| **Erstellt** | 2026-04-10 |
| **Autor** | Mick Gottschalk |
| **Repository** | [github.com/mick-gsk/drift](https://github.com/mick-gsk/drift) |
| **Referenz-SPEC** | `decisions/guided-mode-spec-v02.md` |

---

## 1. Problemstellung

### 1.1 Kontext

drift analysiert strukturelle Abweichungen in Python-Codebasen mittels statischer AST-Analyse. Die vorhandene Signal-Engine erkennt zuverlässig Muster wie Pattern Fragmentation, Architectural Violation und verwandte Degradationsformen. Die Ausgabe richtet sich implizit an Entwickler mit Architekturverständnis — sie enthält Signal-Codes, numerische Score-Werte und technische Terminologie.

### 1.2 Identifizierte Lücke

Eine wachsende Nutzergruppe generiert Code primär über KI-Assistenten (Claude, ChatGPT, Copilot) ohne formale Programmierausbildung. Diese Gruppe bezeichnet sich selbst als „Vibe-Coder". Sie nimmt dasselbe Symptom wahr wie erfahrene Entwickler — ein KI-Assistent, der mit fortschreitender Projektgröße zunehmend inkonsistente oder fehlerhafte Ausgaben produziert — kann aber die Ursache weder diagnostizieren noch beheben.

drift ist in der Lage, exakt dieses Problem zu erkennen. Das `vibe-coding`-Profil in `src/drift/profiles.py` ist bereits auf diese Codebasistypen kalibriert. Die Lücke besteht ausschließlich auf der Ausgabe-Ebene: Die richtigen Signale werden gefunden, aber nicht in einer Form kommuniziert, die ohne Vorwissen verwertbar ist.

### 1.3 Quantifizierung der Lücke

Die aktuelle Ausgabe von `drift analyze` enthält:
- Signal-Codes (z. B. `PFS`, `AVS`, `NCS`) ohne Inline-Erklärung
- Numerische Scores ohne Interpretationsrahmen (z. B. `0.52`, `Δ -0.031`)
- Technische Terminologie ohne Alltagsäquivalent (z. B. „Pattern Fragmentation", „Layer Boundary Violation")
- Dateipfade ohne funktionale Beschreibung

Für Persona A (vgl. Abschnitt 3) ergibt sich daraus eine Nutzungsbarriere, die durch UX-Änderungen — nicht durch Analyse-Änderungen — beseitigt werden kann.

---

## 2. Zielsetzung

### 2.1 Produktziel

Einführung eines neuen Kommandos `drift status` sowie eines interaktiven Setup-Kommandos `drift setup`, die gemeinsam eine vollständige Nutzungserfahrung für Persona A ermöglichen — von der Installation bis zur ersten umsetzbaren Handlungsempfehlung in unter zwei Minuten.

### 2.2 Abgrenzung

Guided Mode ist eine **Ausgabe-Schicht**. Die Analyse-Engine (`pipeline.py`, `signals/`, `scoring/`, `analyzers/`), das Datenmodell (`models.py`) sowie alle bestehenden Kommandos bleiben unverändert. Guided Mode übersetzt vorhandene Analyseergebnisse — er verändert sie nicht.

### 2.3 Nicht-Ziele für v3.0.0

- Kein LLM-gestützter Analyse- oder Textgenerierungspfad
- Keine grafische Benutzeroberfläche
- Keine Änderung bestehender CLI-Kommandos oder deren Ausgabe
- Keine englischsprachige Ausgabe (geplant für v3.1.0)
- Keine MCP-Server-Integration für `drift status` (geplant für v3.1.0)

---

## 3. Nutzergruppen

### 3.1 Persona A — Vibe-Coder *(Primärzielgruppe dieser Funktion)*

**Beschreibung:** Entwickelt eine eigene Anwendung ausschließlich mit KI-Assistenz. Keine formale Programmierausbildung. Versteht Architektur-Konzepte nicht, erkennt aber Symptome — der Assistent wird mit der Zeit unzuverlässiger.

**Ziel:** Verstehen, ob das Projekt „gesund" ist und welche Anweisung an den Assistenten das Problem behebt.

**Erwartete Journey:**
```
$ pip install drift-analyzer
$ drift setup          # maximal 2 Fragen, 30 Sekunden
$ drift status         # Ampelstatus + 1 copy-paste-fertiger Prompt
```

**Erfolgskriterium:** Nutzer kommt ohne Dokumentationslektüre von der Installation bis zum ersten verwertbaren Prompt.

---

### 3.2 Persona B — Entwickler mit KI-Unterstützung

**Beschreibung:** Programmiert selbst, nutzt KI-Assistenten zur Beschleunigung. Kennt Architektur-Konzepte. Will einen schnellen Statusüberblick ohne vollständige Analyse.

**Ziel:** `drift status` als Schnellcheck vor einem Commit oder nach einem größeren Refactoring.

**Erfolgskriterium:** Ausgabe in < 5 Sekunden, kein unnötiger Kontext.

---

### 3.3 Persona C — Erfahrener Entwickler / Team *(Bestandsnutzer)*

**Beschreibung:** Nutzt drift bereits. Kennt alle Kommandos. Hat keinen Bedarf an Guided Mode.

**Anforderung:** Null Verhaltensänderung an bestehenden Kommandos. `drift analyze`, `drift check`, `drift fix-plan`, `drift explain` verhalten sich exakt wie in v2.x.

---

## 4. Funktionale Anforderungen

### 4.1 `drift status` — Kernkommando

**Priorität: P0** | Zieldatei: `src/drift/commands/status.py` (neu)

| ID | Anforderung |
|---|---|
| F-01 | Das Kommando gibt als primäres Element einen Ampelstatus aus (🟢 / 🟡 / 🔴) |
| F-02 | Die Statusbestimmung basiert auf der höchsten Finding-Severity sowie dem Gesamt-Score; RED hat immer Vorrang |
| F-03 | Die Ausgabe enthält keinen Signal-Code im Standard-Modus |
| F-04 | Die Ausgabe enthält keinen numerischen Score-Wert im Standard-Modus |
| F-05 | Die Ausgabe enthält für das Finding mit dem höchsten `score_contribution`-Wert einen copy-paste-fertigen Prompt in Alltagssprache |
| F-06 | Der Prompt enthält keinen rohen Dateipfad; Dateien werden über ihre funktionale Rolle beschrieben |
| F-07 | Der Prompt enthält einen Satz, der beschreibt, was nach der Ausführung besser sein sollte |
| F-08 | Der Exit Code beträgt immer 0 |
| F-09 | Bei mehr als einem Finding erscheint ein Hinweis auf `drift status --all` und `drift analyze` |

**Ampel-Schwellwerte (vibe-coding-Profil, Designannahme — empirisch zu validieren):**

| Status | Bedingung |
|---|---|
| 🟢 GREEN | Score < 0.35 UND kein Finding mit Severity HIGH |
| 🟡 YELLOW | Score 0.35–0.64 ODER mindestens ein Finding mit Severity HIGH |
| 🔴 RED | Score ≥ 0.65 ODER mindestens ein Finding mit Severity CRITICAL |

*Anmerkung: Diese Schwellwerte sind für `profile: vibe-coding` kalibriert. Bei anderen Profilen bleibt `drift status` lauffähig, gibt jedoch einen Hinweis auf unvollständige Kalibrierung aus.*

---

### 4.2 `drift status --all`

**Priorität: P1**

| ID | Anforderung |
|---|---|
| F-10 | Gibt alle Findings im Guided-Mode-Format aus, standardmäßig maximal 5 (steuerbar via `--limit`) |
| F-11 | Jedes Finding enthält eine eigene Prompt-Box |
| F-12 | Sortierung: Severity absteigend, dann `score_contribution` absteigend |

---

### 4.3 `drift status --format json`

**Priorität: P1**

Das JSON-Schema folgt dem in der SPEC definierten Format. Wesentliche Eigenschaften:

| Eigenschaft | Typ | Beschreibung |
|---|---|---|
| `status` | `"green"` / `"yellow"` / `"red"` | Ampelstatus |
| `headline` | `string` | Alltagssprachliche Statusbeschreibung |
| `can_continue` | `boolean` | Semantisches Signal für integrierende Tools |
| `top_finding` | `object` | Finding mit höchstem `score_contribution` |
| `top_finding.plain_text` | `string` | Alltagssprachliche Beschreibung, kein Signal-Code |
| `top_finding.agent_prompt` | `string` | Copy-paste-fertiger Prompt, keine Dateipfade |
| `total_findings` | `integer` | Gesamtanzahl der Findings |
| `shown_findings` | `integer` | Anzahl der im Output enthaltenen Findings |
| `lang` | `string` | Verwendete Ausgabesprache (ISO 639-1) |

---

### 4.4 `drift setup` — Onboarding

**Priorität: P0** | Zieldatei: `src/drift/commands/setup.py` (neu)

| ID | Anforderung |
|---|---|
| F-13 | Das Kommando stellt maximal 2 Fragen im interaktiven Dialog |
| F-14 | Frage 1: Zielgruppe des Projekts (Auswahlmenü, empfiehlt `vibe-coding` für Nicht-Entwickler) |
| F-15 | Frage 2: Sofortigen ersten Scan ausführen? (Ja / Nein) |
| F-16 | Das Kommando erstellt eine valide `drift.yaml` mit `profile` und `language` |
| F-17 | Bei bestehender `drift.yaml` wird explizit nachgefragt, bevor überschrieben wird |
| F-18 | Vor dem Überschreiben wird `drift.yaml.bak` als atomare Operation erstellt |
| F-19 | Die abschließende Ausgabe benennt `drift status` als nächsten Schritt |
| F-20 | Bei Abbruch durch den Nutzer beträgt der Exit Code 1 |

---

### 4.5 Sprachauflösung

**Priorität: P1**

Die Ausgabesprache wird nach folgender Priorität aufgelöst (höchste zuerst):

1. CLI-Flag `--lang <code>`
2. `language`-Feld in `drift.yaml`
3. Profil-Default (`vibe-coding` → `"de"`)
4. Systemweiter Fallback → `"de"`

Für v3.0.0 ist ausschließlich `"de"` produktiv implementiert. Bei `--lang en` wird ein Stub-Hinweis ausgegeben, und die Ausgabe fällt auf Deutsch zurück.

---

### 4.6 Rückwärtskompatibilität

**Priorität: P0** — Nicht verhandelbar.

| ID | Anforderung |
|---|---|
| F-21 | `drift analyze`, `drift check`, `drift fix-plan`, `drift explain` verhalten sich exakt wie in v2.x |
| F-22 | Bestehende `drift.yaml`-Dateien ohne `language`-Feld funktionieren ohne Fehler |
| F-23 | Die `Profile`-Dataclass in `profiles.py` erhält nur optionale Felder mit Defaults |
| F-24 | Kein neues obligatorisches Top-Level-Dependency in `pyproject.toml` |

---

## 5. Nicht-funktionale Anforderungen

| ID | Anforderung | Zielwert |
|---|---|---|
| NF-01 | Laufzeit-Overhead von `drift status` gegenüber `drift analyze` | < 50 ms (reiner Rendering-Overhead) |
| NF-02 | Terminal-Darstellung bei 80-Zeichen-Breite | Kein Zeilenüberlauf; automatisierter CI-Test |
| NF-03 | Alle Signal-Typen besitzen vollständige deutsche Ausgabetexte | Automatisierter Vollständigkeitstest (15/15) |
| NF-04 | `drift setup` vollständig abschließbar | In < 60 Sekunden ab Kommandostart |
| NF-05 | Kein Datenverlust bei `drift setup --overwrite`-Pfad | `drift.yaml.bak` muss vor Schreiboperation existieren |

---

## 6. Architektur-Übersicht

Die folgenden Dateien werden neu erstellt. Alle anderen Dateien bleiben unverändert.

```
src/drift/
├── commands/
│   ├── status.py          # NEU — drift status Kommando
│   └── setup.py           # NEU — drift setup Kommando
├── output/
│   ├── guided_output.py   # NEU — Ampel-Logik, Alltagstext-Mapping
│   └── prompt_generator.py # NEU — Template-basierte Prompt-Generierung
```

Die folgenden Dateien werden minimal erweitert, ohne bestehende Signaturen zu ändern:

```
src/drift/
├── cli.py                 # Registrierung der neuen Kommandos
├── profiles.py            # Optionale Felder: guided_thresholds, output_language
├── config.py              # Optionales Feld: language
└── finding_rendering.py   # Neue Funktion _finding_guided() neben bestehenden
```

---

## 7. Designentscheidungen

### 7.1 Keine LLM-basierte Textgenerierung

Template-basierte Ausgabetexte sind deterministisch, erfordern keine externe Verbindung und produzieren keine Halluzinationen. Die Qualitätsobergrenze gut entworfener Templates ist für diesen Use Case ausreichend und überprüfbar.

### 7.2 Exit Code 0 für alle Ampelstatus

`drift status` ist ein Informationskommando für menschliche Nutzer. Maschinenlesbare Gates werden durch `drift check` mit `fail-on`-Konfiguration abgebildet. Ein Exit Code ≠ 0 bei RED würde Persona A in Szenarien ohne CI-Kontext irreführen.

### 7.3 Score wird in der Guided-Ausgabe nicht angezeigt

Die Ampel ist die Abstraktion des Scores. Beide gleichzeitig anzuzeigen würde die Semantik der Ampel entwerten und Persona A mit einem Wert konfrontieren, den sie nicht einordnen kann. Wer den Score benötigt, nutzt `drift analyze`.

### 7.4 Schwellwerte sind nicht nutzer-konfigurierbar

Guided Mode richtet sich an Nutzer, die keine Konfiguration vornehmen wollen oder können. Konfigurierbare Schwellwerte würden Komplexität in ein Kommando einführen, das explizit konfigurationsarm sein soll. Für Persona B und C existiert `drift check --fail-on`.

### 7.5 `can_continue=False` ab YELLOW

Das semantische Signal `can_continue` richtet sich an integrierende Tools, nicht an Endnutzer. Ab YELLOW besteht ein strukturelles Problem, das sich ohne Eingriff verschlimmert. Die alltagssprachliche Headline kommuniziert keine Dringlichkeit — das semantische Signal tut es. Beide Dimensionen sind bewusst entkoppelt.

---

## 8. Kommando-Übersicht

| Kommando | Primäre Zielgruppe | Ausgabetyp | Exit-Code-Verhalten |
|---|---|---|---|
| `drift analyze` | Entwickler | Technisch, vollständig | 0 |
| `drift check` | Teams / CI | Technisch, gate-fähig | 0 / 1 je `fail-on` |
| `drift fix-plan` | Agenten / Entwickler | Maschinenlesbar | 0 |
| `drift explain` | Entwickler | Technisch, erklärt | 0 |
| **`drift status`** | **Vibe-Coder / Schnellcheck** | **Alltagssprache, Ampel** | **0** |
| **`drift setup`** | **Vibe-Coder / Erstnutzer** | **Interaktiver Dialog** | **0 / 1 bei Abbruch** |

---

## 9. Risiken

| # | Risiko | Eintrittswahrscheinlichkeit | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | Ampel-Schwellwerte fehlkalibriert — zu viele false-positive RED-Status | Mittel | Hoch | Post-Release: empirische Auswertung auf ≥ 10 Repositories; Schwellwerte via Patch anpassbar ohne API-Break |
| R-02 | Generierte Prompts produzieren schlechtere Agenten-Ergebnisse als kein Prompt | Niedrig | Hoch | Manuelle Review aller Prompt-Templates vor Release; Feedback-Kanal in README |
| R-03 | Persona A versteht Ampelstatus, aber nicht den nachfolgenden Schritt | Mittel | Mittel | Usability-Test mit ≥ 2 nicht-technischen Testnutzern vor v3.0.0-Release |
| R-04 | `drift setup` überschreibt durch einen Bug `drift.yaml` ohne vorheriges Backup | Niedrig | Hoch | `drift.yaml.bak` wird als atomare Operation vor jeder Schreiboperation angelegt; Testfall als Pflicht |

---

## 10. Offene Entscheidungen

| # | Frage | Optionen | Empfehlung | Fälligkeit |
|---|---|---|---|---|
| OD-01 | Soll `drift` ohne Argument bei `profile: vibe-coding` auf `drift status` delegieren? | Ja / Nein | Ja — senkt Einstiegshürde ohne Breaking Change für andere Profile | Vor v3.0.0-Tag |
| OD-02 | MCP-Server-Integration von `drift status --format json` | v3.0.0 / v3.1.0 | v3.1.0 — separates Ticket, kein Scope Creep | Nach v3.0.0 |

---

## 11. Implementierungsmeilensteine

| # | Meilenstein | Abhängigkeit | Anmerkung |
|---|---|---|---|
| M1 | `guided_output.py` — Ampel-Logik + Alltagstext-Mapping + Tests | — | Kritischer Pfad |
| M2 | `prompt_generator.py` — Template-Engine + alle 15 Signal-Typen + Tests | M1 | |
| M3 | `commands/status.py` — text + json Output lauffähig | M2 | |
| M4 | `profiles.py` + `config.py` — optionale Felder mit Defaults | Parallel zu M1 | |
| M5 | `commands/setup.py` — interaktiver Dialog, Backup-Logik | M3, M4 | |
| M6 | `finding_rendering.py` — `_finding_guided()` Erweiterung | M2 | |
| M7 | `cli.py` — Kommando-Registrierung, `--help`-Texte | M3, M5 | |
| M8 | Vollständige Testabdeckung, manuelle Prompt-Review, OD-01 entschieden | M1–M7 | Release-Gate |
| **M9** | **Release v3.0.0** | **M8** | |

---

## 12. Erfolgskriterien nach Release

| Metrik | Zielwert | Messzeitraum |
|---|---|---|
| PyPI-Downloads (30-Tage-Fenster nach Release) | +25 % gegenüber letztem v2.x-Release | 30 Tage |
| Neue GitHub Issues der Kategorie „Ausgabe nicht verständlich" | 0 | 60 Tage |
| Externe Erwähnungen / positive Nutzerbewertungen zu `drift status` | ≥ 3 | 90 Tage |

---

*Dokument-Version: 1.1 — Letzte Änderung: 2026-04-10*

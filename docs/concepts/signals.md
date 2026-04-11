# Signals

Signals sind das Herzstück von drift. Diese Seite erklärt, was ein Signal ist, wie es ausgelöst wird und was jedes der 24 eingebauten Signals misst.

---

## Was ist ein Signal?

Ein Signal ist eine strukturelle Heuristik, die ein konkretes Erosionsmuster im Quellcode erkennt — kein Syntaxfehler, keine Stilregel, sondern ein messbares Kohärenzproblem.

Ein Linter prüft, ob Code einer Regel entspricht (z. B. „keine ungenutzten Importe"). Ein Signal misst dagegen, ob strukturelle Entscheidungen konsistent und intentional sind. Linting ist regelbasiert und deterministisch; Signals sind musterbasiert und komparativ. Ein Signal schlägt an, wenn ein Muster im Kontext des gesamten Repositories von etablierten Strukturen abweicht — nicht nur weil eine Zeile formal falsch ist.

---

## Wie wird ein Signal ausgelöst?

Drift führt für jedes aktivierte Signal eine Analyse durch, die folgende Quellen kombiniert:

- **AST-Analyse** — Syntaxbaum des Quellcodes (Funktionsstrukturen, Importe, Komplexität)
- **Git-History** — Commit-Frequenz, Autoren, Änderungsmuster der letzten `since_days` Tage (Standard: 90)
- **Semantische Ähnlichkeit** — Embedding-basierter Vergleich von Funktionskörpern (bei aktivierten Embeddings)

Wenn eine Heuristik oberhalb eines kalibrierten Schwellwerts liegt, erzeugt das Signal ein `Finding` mit Score (0.0–1.0), Severity und einem konkreten Handlungshinweis.

---

## Tabelle aller Signals

**Kategorie: `structural_risk`** — Risiken durch strukturelle Inkohärenz

| Signal-ID | Abk. | Was wird gemessen | Wann kritisch |
|-----------|------|-------------------|---------------|
| `pattern_fragmentation` | **PFS** | Mehrere inkompatible Implementierungsvarianten derselben Musterkategorie (z. B. Fehlerbehandlung) im selben Modul | Wenn ≥ 3 Varianten einer Kategorie existieren, typisch nach Multi-Session KI-Generierung |
| `mutant_duplicate` | **MDS** | Nahezu identische Funktionen (AST-Jaccard ≥ 80%) innerhalb derselben Datei | Wenn Funktionen sich nur in Kleinigkeiten unterscheiden statt parametrisiert zu sein |
| `temporal_volatility` | **TVS** | Anomale Änderungsfrequenz (z-Score) relativ zum Repository-Durchschnitt | Bei > 3x durchschnittlicher Änderungsrate mit vielen Autoren _(report-only, kein Score-Beitrag)_ |
| `system_misalignment` | **SMS** | Neue Commits führen Muster, Dependencies oder Konventionen ein, die im Zielmodul nicht etabliert sind | Wenn ein PR eine fremde HTTP-Bibliothek oder eine andere Fehlerbehandlungsstrategie in ein etabliertes Modul einführt |
| `test_polarity_deficit` | **TPD** | Test-Suiten, die ausschließlich den Happy Path testen — keine negativen Tests, keine Boundary-Checks | Wenn eine Datei ≥ 5 Testfunktionen hat, aber kein einziges `pytest.raises` oder `assertRaises` |
| `bypass_accumulation` | **BAT** | Häufung von Quality-Bypass-Markern (`# type: ignore`, `# noqa`, `# pragma: no cover`) über einem Dichte-Schwellwert | Wenn > 0.05 Marker pro LOC, was auf technische Schuld durch geflickte KI-Ausgaben hindeutet |
| `exception_contract_drift` | **ECM** | Inkonsistente Exception-Verträge zwischen Modulen (einige re-raisen, andere schlucken) | Bei modulweiter Inkonsistenz, die Fehlerdiagnose erschwert |
| `ts_architecture` | **TSA** | TypeScript-spezifische Architekturprobleme _(report-only)_ | — |

**Kategorie: `architecture_boundary`** — Grenzüberschreitungen zwischen Schichten

| Signal-ID | Abk. | Was wird gemessen | Wann kritisch |
|-----------|------|-------------------|---------------|
| `architecture_violation` | **AVS** | Importe, die deklarierte Layer-Grenzen überschreiten (z. B. Route importiert direkt aus DB), zirkuläre Abhängigkeiten, Blast-Radius-Hubs | Wenn eine Route-Datei direkt Datenbankmodelle importiert statt des Service-Layers |
| `circular_import` | **CIR** | Zirkuläre Import-Ketten _(report-only)_ | Bei Import-Zyklen, die Laufzeitfehler verursachen können |
| `co_change_coupling` | **CCC** | Dateien, die in der Git-History immer gemeinsam geändert werden (git-abhängig) | Wenn zwei Dateien in >70% der Commits gemeinsam auftreten — verborgene Kopplung |
| `cohesion_deficit` | **COD** | Module mit geringer interner Kohäsion (unzusammenhängende Verantwortlichkeiten) | Bei Modulen, die mehrere unverbundene Konzepte mischen |
| `fan_out_explosion` | **FOE** | Module mit exzessiv vielen ausgehenden Dependencies _(report-only)_ | Wenn ein Modul > 15 direkte Imports hat und damit zur Änderungs-Schnittstelle wird |

**Kategorie: `style_hygiene`** — Wartbarkeit und Ausdrucksfähigkeit

| Signal-ID | Abk. | Was wird gemessen | Wann kritisch |
|-----------|------|-------------------|---------------|
| `naming_contract_violation` | **NBV** | Funktionen, deren Name einen Vertrag impliziert, den die Implementierung nicht erfüllt (`validate_*`, `is_*`, `get_*`) | Wenn `validate_email()` nie raise oder False zurückgibt |
| `doc_impl_drift` | **DIA** | Divergenz zwischen Architekturdokumentation (ADRs, README) und tatsächlichem Code | Wenn README „nutzt SQLite" sagt, aber PostgreSQL importiert wird |
| `explainability_deficit` | **EDS** | Hochkomplexe Funktionen ohne Docstring, Typ-Annotationen oder Tests, insbesondere KI-attribuierte | Funktionen mit Cyclomatic Complexity > 10 und > 10 LOC ohne Dokumentation |
| `broad_exception_monoculture` | **BEM** | Gehäufte Nutzung von `except Exception` ohne Re-raise | Wenn ein Modul durchgehend alle Exceptions schluckt statt spezifische zu fangen |
| `guard_clause_deficit` | **GCD** | Öffentliche, nicht-triviale Funktionen ohne Input-Validierung am Eingang | Wenn < 15% der qualifizierenden Funktionen eines Moduls Eingabevalidierung haben |
| `dead_code_accumulation` | **DCA** | Angehäufter ungenutzter Code _(report-only)_ | Bei umfangreichem totem Code, der Wartungsaufwand erhöht ohne Nutzen |
| `cognitive_complexity` | **CXS** | Kognitive Komplexität nach SonarQube-Metrik _(report-only)_ | Bei > 20 für einzelne Funktionen |

**Kategorie: `security`** — Sicherheitsmen Schwachstellen _(alle report-only)_

| Signal-ID | Abk. | Was wird gemessen | Wann kritisch |
|-----------|------|-------------------|---------------|
| `missing_authorization` | **MAZ** | Endpoints oder Funktionen ohne Autorisierungsprüfung _(report-only)_ | Bei öffentlich exponierten Routen ohne Auth-Dekorator |
| `insecure_default` | **ISD** | Unsichere Standardkonfigurationen _(report-only)_ | Bei `debug=True`, offenen CORS-Wildcard-Konfigurationen u. ä. |
| `hardcoded_secret` | **HSC** | Hartcodierte Geheimnisse und Credentials _(report-only)_ | Wenn API-Keys oder Passwörter direkt im Code stehen |

**Kategorie: `ai_quality`**

| Signal-ID | Abk. | Was wird gemessen | Wann kritisch |
|-----------|------|-------------------|---------------|
| `phantom_reference` | **PHR** | Nicht auflösbare Funktions- oder Klassen-Referenzen (KI-Halluzinations-Indikator) _(report-only)_ | Wenn Code Symbole referenziert, die nirgendwo im Repository definiert sind |

> Signals mit dem Vermerk **_(report-only)_** werden im Output angezeigt, tragen aber mit Gewicht `0.0` nicht zum Composite Score bei. Sie dienen der Beobachtung ohne automatisches Blockieren.

---

## Signal-Gewichtung

Jedes scoring-aktive Signal hat ein Standardgewicht (0.0–1.0), das seinen Anteil am [Composite Drift Score](scoring.md) bestimmt. Die Gewichte sind so kalibriert, dass Signals mit höherem Strukturrisiko stärker ins Gewicht fallen:

```
PFS: 0.16   AVS: 0.16   MDS: 0.13   EDS: 0.09
SMS: 0.08   TPD: 0.04   DIA: 0.04   BEM: 0.04
NBV: 0.04   GCD: 0.03   BAT: 0.03   ECM: 0.03
COD: 0.01   CCC: 0.005
```

Alle Signale mit `0.0` sind report-only und beeinflussen den Score nicht.

### Gewichte anpassen

Mit `drift calibrate run` berechnet drift aus gesammeltem Feedback (z. B. manuell bestätigten oder abgelehnten Findings) projektspezifische Gewichte und schreibt sie in `drift.yaml`:

```bash
drift calibrate run         # Kalibrierung berechnen und anzeigen
drift calibrate run --apply # Kalibrierte Gewichte in drift.yaml schreiben
```

Gewichte können auch direkt in `drift.yaml` gesetzt werden:

```yaml
weights:
  pattern_fragmentation: 0.20   # Höher gewichten
  doc_impl_drift: 0.01          # Niedriger gewichten
  temporal_volatility: 0.0      # Komplett ausblenden (report-only)
```

---

## Nächste Schritte

- [**scoring.md**](scoring.md) — Wie Gewichte zu einem Composite Score zusammengerechnet werden
- [**baseline.md**](baseline.md) — Bestehende Findings als Baseline erfassen und neue isolieren
- [**../guides/quickstart.md**](../guides/quickstart.md) — Erste Schritte mit drift
- [**../guides/ci-integration.md**](../guides/ci-integration.md) — Signals in CI-Pipelines einsetzen

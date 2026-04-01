# STRIDE Threat Model — drift-analyzer

> **Systematic Threat Analysis** auf Systemgrenzen, Datenflüsse und Komponenten.
> Methode: STRIDE per Element (Microsoft SDL).
> Lebendes Dokument — Review bei Architekturänderungen oder neuen Input-Pfaden.

**Erstellt:** 2026-04-01  
**Scope:** drift-analyzer v1.3.x als CLI-Tool, CI-Action und MCP-Server  
**Annahme:** Angreifer hat Write-Zugriff auf das analysierte Repository (aber nicht auf den Rechner, der drift ausführt)

---

## 1. Datenflussdiagramm (DFD)

```
                        ┌─────────────────────────────────────────────┐
                        │          TRUST BOUNDARY 1: CLI/API          │
                        │  ┌──────────┐  ┌─────────┐  ┌───────────┐  │
   User/CI ──(args)───▶ │  │  cli.py  │  │ api.py  │  │mcp_server │  │
                        │  └────┬─────┘  └────┬────┘  └─────┬─────┘  │
                        └───────┼──────────────┼─────────────┼────────┘
                                │              │             │
                                ▼              ▼             ▼
                        ┌─────────────────────────────────────────────┐
                        │    TRUST BOUNDARY 2: CONFIG PARSING         │
                        │  ┌────────────────────────────────────────┐ │
   drift.yaml ────────▶ │  │  DriftConfig.load()                   │ │
   drift.toml ────────▶ │  │  yaml.safe_load / tomllib.loads       │ │
   pyproject.toml ────▶ │  │  Pydantic strict (extra="forbid")     │ │
                        │  └────────────────┬───────────────────────┘ │
                        └───────────────────┼─────────────────────────┘
                                            │
                                            ▼
                        ┌─────────────────────────────────────────────┐
                        │    TRUST BOUNDARY 3: REPOSITORY FILESYSTEM  │
                        │                                             │
                        │  ┌──────────────┐  ┌─────────────────────┐  │
   .py/.ts files ─────▶ │  │file_discovery│  │    ast_parser       │  │
   Verzeichnisse ─────▶ │  │(symlink-skip)│  │(ast.parse/treesit.) │  │
   .git/ ─────────────▶ │  └──────┬───────┘  └─────────┬───────────┘  │
                        └─────────┼─────────────────────┼──────────────┘
                                  │                     │
                                  ▼                     ▼
                        ┌─────────────────────────────────────────────┐
                        │    TRUST BOUNDARY 4: GIT SUBPROCESS         │
                        │  ┌────────────────────────────────────────┐ │
   git log ───────────▶ │  │  subprocess.run(["git", "log", ...])  │ │
   (60s Timeout)        │  │  Hardcoded Format-Strings              │ │
   Co-author Headers ─▶ │  │  AI-Attribution-Regex                  │ │
                        │  └────────────────┬───────────────────────┘ │
                        └───────────────────┼─────────────────────────┘
                                            │
                                            ▼
                        ┌─────────────────────────────────────────────┐
                        │            SIGNAL EXECUTION                 │
                        │  ┌────────────────────────────────────────┐ │
                        │  │  22 Signale × ThreadPoolExecutor(8)   │ │
                        │  │  AnalysisContext → list[Finding]      │ │
                        │  └────────────────┬───────────────────────┘ │
                        └───────────────────┼─────────────────────────┘
                                            │
                                            ▼
                        ┌─────────────────────────────────────────────┐
                        │            SCORING & DEDUPLICATION          │
                        │  impact = weight × score × breadth_factor  │
                        │  Dedup: (rule_id, file, line, title)       │
                        └───────────────────┬─────────────────────────┘
                                            │
                                            ▼
                        ┌─────────────────────────────────────────────┐
                        │    TRUST BOUNDARY 5: OUTPUT                 │
                        │  ┌──────┐ ┌──────┐ ┌──────┐ ┌───────────┐  │
                        │  │ JSON │ │ SARIF│ │GitHub│ │ Telemetry │  │
                        │  │stdout│ │ file │ │Annot.│ │  JSONL    │  │
                        │  └──────┘ └──────┘ └──────┘ └───────────┘  │
                        └─────────────────────────────────────────────┘

  Data Stores:
  [DS-1] Parse-Cache:     Datei-AST-Fingerprints (hash → ParseResult)
  [DS-2] Baseline JSON:   .drift/baseline.json (Score-Historie)
  [DS-3] Telemetrie JSONL: .drift/telemetry.jsonl (opt-in)
```

---

## 2. STRIDE per Trust Boundary

### TB-1: CLI/API Eingang

| Threat | Kategorie | Beschreibung | Schwere | Wahrsch. | Bestehende Kontrolle | Residual Risk | Empfehlung |
|--------|-----------|--------------|---------|----------|---------------------|---------------|------------|
| S-TB1-01 | **Spoofing** | Angreifer gibt falschen `--repo-path` an, um beliebiges Verzeichnis analysieren zu lassen | Niedrig | Niedrig | Path muss existierendes Git-Repo sein; User hat bereits Shell-Zugriff | **Akzeptabel** — gleiche Rechte wie lokale Shell | — |
| T-TB1-01 | **Tampering** | Manipulierte CLI-Argumente (`--signals`, `--fail-on`) ändern Analyseverhalten | Niedrig | Niedrig | Click-Typ-Validierung; Signal-Whitelist (`VALID_SIGNAL_IDS`) | **Akzeptabel** — User hat sowieso volle Kontrolle | — |
| R-TB1-01 | **Repudiation** | Keine Audit-Logs wer wann welche Analyse ausgeführt hat | Niedrig | Mittel | Telemetrie (opt-in) loggt Tool-Name, Params, Status | **Akzeptabel** — für lokales Tool nicht kritisch; CI-Logs reichen | — |
| I-TB1-01 | **Info Disclosure** | CLI-Hilfe oder Fehlermeldungen leaken interne Pfade | Niedrig | Niedrig | Fehlermeldungen enthalten Repo-Path (user-provided) | **Akzeptabel** | — |
| D-TB1-01 | **DoS** | Riesiger `--max-files` Wert → Ressourcenerschöpfung | Mittel | Niedrig | Default 10.000; User-kontrolliert | **Niedrig** | Obere Grenze dokumentieren |
| E-TB1-01 | **Elev. of Privilege** | MCP-Server exponiert Scan-Funktion → unberechtigter Zugriff auf lokale Repos | Mittel | Niedrig | MCP läuft lokal (stdio); kein Netzwerk-Listener | **Niedrig** | MCP-Berechtigungsmodel dokumentieren |

### TB-2: Config Parsing

| Threat | Kategorie | Beschreibung | Schwere | Wahrsch. | Bestehende Kontrolle | Residual Risk | Empfehlung |
|--------|-----------|--------------|---------|----------|---------------------|---------------|------------|
| S-TB2-01 | **Spoofing** | Angreifer platziert `drift.yaml` in Fork/PR → Analyse-Konfiguration geändert | Mittel | Mittel | Config wird aus Repo-Root geladen; Reviewer muss Config-Änderung prüfen | **Mittel** | PRs mit Config-Änderungen flaggen; `--no-repo-config` Option |
| T-TB2-01 | **Tampering** | Config mit `exclude_signals: [AVS, PFS]` → kritische Signale deaktiviert | Hoch | Mittel | Pydantic-Validierung; aber `exclude_signals` ist valides Feature | **Mittel** — bewusste Blindspot-Erzeugung möglich | Warnung wenn >50% der Core-Signale deaktiviert |
| T-TB2-02 | **Tampering** | Config mit manipulierten `signal_weights` → Score-Verzerrung | Mittel | Niedrig | Weights normalisiert; Warnung bei starker Abweichung | **Niedrig** | Deviance-Warnung beibehalten |
| T-TB2-03 | **Tampering** | BOM in `pyproject.toml` → DRIFT-1002, Analyse bricht ab | Mittel | Niedrig | **Kein Schutz** — tomllib.loads scheitert an BOM | **Offen** ⚠️ | BOM-Strip implementieren |
| I-TB2-01 | **Info Disclosure** | Config-Fehlermeldung zeigt vollständigen Config-Inhalt | Niedrig | Niedrig | Error-Boundary zeigt nur Fehlerstelle | **Akzeptabel** | — |
| D-TB2-01 | **DoS** | Riesige YAML-Datei (100 MB+) → Parser-Erschöpfung | Niedrig | Sehr niedrig | `yaml.safe_load` hat keine Size-Limits; Config-Dateien typisch <10 KB | **Niedrig** | Optional: Config-Datei-Größenlimit (1 MB) |

### TB-3: Repository Filesystem

| Threat | Kategorie | Beschreibung | Schwere | Wahrsch. | Bestehende Kontrolle | Residual Risk | Empfehlung |
|--------|-----------|--------------|---------|----------|---------------------|---------------|------------|
| S-TB3-01 | **Spoofing** | Dateien tragen irreführende Endungen (.py enthält kein Python) | Niedrig | Niedrig | ast.parse wirft SyntaxError → Datei übersprungen; DegradationInfo | **Akzeptabel** | — |
| T-TB3-01 | **Tampering** | Symlink `.py` → `/etc/passwd` oder sensible Datei | Hoch | Niedrig | **Symlinks werden übersprungen** (`is_symlink()` check) | **Mitigiert** ✅ | — |
| T-TB3-02 | **Tampering** | Gezielt platzierte Dateien um Signale zu blenden (z.B. leere `__init__.py` überall) | Mittel | Niedrig | Ist im Prinzip ein valides Repo-Muster; Findings sind dann korrekt reduziert | **Akzeptabel** — ehrliche Analyse des vorgefundenen Zustands | — |
| T-TB3-03 | **Tampering** | Tief verschachtelter AST (100+ Nesting-Ebenen) → Parser-Stack-Overflow | Mittel | Sehr niedrig | Python ast.parse hat Default-Rekursionslimit (1000) | **Niedrig** | — |
| I-TB3-01 | **Info Disclosure** | Quelldateien werden gelesen → Code-Inhalt in Findings sichtbar | Mittel | Mittel | Findings zeigen Datei:Zeile, aber keinen Code-Body (nur Titles/Descriptions) | **Niedrig** — Symbolnamen und Pfade im Output sind beabsichtigt | Sensitivitäts-Warnung in Docs |
| D-TB3-01 | **DoS** | Repo mit 100.000+ Dateien → OOM/Laufzeit-Explosion | Mittel | Niedrig | `max_discovery_files=10.000`; 5 MB File-Size-Limit | **Mitigiert** ✅ | — |
| D-TB3-02 | **DoS** | Datei mit 5 MB Python → langsames AST-Parsing pro Thread | Niedrig | Niedrig | 5 MB Limit; 8 Worker-Threads | **Niedrig** | — |

### TB-4: Git Subprocess

| Threat | Kategorie | Beschreibung | Schwere | Wahrsch. | Bestehende Kontrolle | Residual Risk | Empfehlung |
|--------|-----------|--------------|---------|----------|---------------------|---------------|------------|
| S-TB4-01 | **Spoofing** | Gefälschte `Co-authored-by: copilot` Headers → falsche AI-Attribution | Mittel | Mittel | Heuristik-basiert (nicht kryptographisch); AI-Ratio beeinflusst nur Reporting | **Mittel** — absichtliche Manipulation möglich und schwer erkennbar | AI-Attribution als „heuristisch" markieren; Confidence-Level anzeigen |
| S-TB4-02 | **Spoofing** | Git-Author-Spoofing → falscher Contributor-Count | Niedrig | Mittel | Git-Signatur-Verification ist nicht Drift's Aufgabe | **Akzeptabel** — out of scope | — |
| T-TB4-01 | **Tampering** | Manipulierte `.git`-Objekte → falsche History-Daten | Mittel | Niedrig | Subprocess liest via `git log` (git's eigene Integrity-Checks) | **Niedrig** | — |
| T-TB4-02 | **Tampering** | Commit-Messages mit Injection-Patterns (z.B. `--format` Overrides) | Hoch | Niedrig | **Hardcoded Format-Strings** in Subprocess-Argument-Liste; kein Shell | **Mitigiert** ✅ | — |
| R-TB4-01 | **Repudiation** | AI-Attribution kann gezielt durch Commit-Message-Patterns verschleiert werden | Mittel | Mittel | Tier-1/Tier-2 Muster; File-Indicators (.claude/, .copilotignore) | **Mittel** — gewollte Verschleierung möglich | In Docs als Einschränkung dokumentieren |
| I-TB4-01 | **Info Disclosure** | Git-History enthält Commit-Messages mit sensiblen Informationen | Niedrig | Niedrig | Drift liest nur Format-Felder (Author, Date, Subject); keine Diff-Bodies | **Niedrig** | — |
| D-TB4-01 | **DoS** | Repository mit 1M+ Commits → `git log` Timeout | Mittel | Niedrig | **60s Timeout**; DegradationInfo loggt `git_timeout` | **Mitigiert** ✅ | Timeout konfigurierbar machen |
| E-TB4-01 | **Elev. of Privilege** | Argument-Injection via Repo-Pfad mit Sonderzeichen | Hoch | Sehr niedrig | **Argument-Liste** (kein Shell); Python subprocess.run() escaped korrekt | **Mitigiert** ✅ | — |

### TB-5: Output Boundary

| Threat | Kategorie | Beschreibung | Schwere | Wahrsch. | Bestehende Kontrolle | Residual Risk | Empfehlung |
|--------|-----------|--------------|---------|----------|---------------------|---------------|------------|
| I-TB5-01 | **Info Disclosure** | `--target-path` analysiert Subdir, aber `related_files` zeigen Pfade außerhalb | Mittel | Mittel | Kein Filter auf related_files bei target-path-Beschränkung | **Offen** ⚠️ | Related-files auf target-path-Scope filtern |
| I-TB5-02 | **Info Disclosure** | Telemetrie-JSONL loggt CLI-Params (Repo-Pfade, Signal-Auswahl) | Niedrig | Niedrig | Opt-in (DRIFT_TELEMETRY_ENABLED); `_REDACT_KEYS` für Secrets | **Niedrig** | — |
| I-TB5-03 | **Info Disclosure** | Negative-Context-Export (`.drift-negative-context.md`) leakt Anti-Patterns | Niedrig | Niedrig | User löst Export explizit aus; keine Code-Bodies | **Akzeptabel** | — |
| I-TB5-04 | **Info Disclosure** | SARIF-Upload zu GitHub Code Scanning macht Findings öffentlich (public repos) | Niedrig | Mittel | Repo-Visibility-Policy ist GitHub-seitig; Drift hat keinen Einfluss | **Akzeptabel** — User-Entscheidung | Sicherheitshinweis in CI-Setup-Docs |
| T-TB5-01 | **Tampering** | Baseline-Datei (`.drift/baseline.json`) kann manipuliert werden → falscher Trend | Mittel | Niedrig | Baseline ist lokale Datei; Integrität nicht kryptographisch gesichert | **Niedrig** | Optional: Baseline-Checksum; oder Warnung bei unplausiblem Delta |
| D-TB5-01 | **DoS** | JSON-Output bei 10.000+ Findings → Multi-MB-Output → Consumer-Overflow | Niedrig | Niedrig | Compact-Mode; Top-N-Filtering; Deduplication | **Niedrig** | — |

---

## 3. Data Store Threats

| Store | Threat | Kategorie | Beschreibung | Kontrolle | Residual Risk |
|-------|--------|-----------|--------------|-----------|---------------|
| DS-1 Parse-Cache | T | Tampering | Cache-Poisoning: veraltete/manipulierte AST-Daten | Git-Commit-Hash als Invalidierungs-Key | **Niedrig** — uncommitted changes nicht cached |
| DS-2 Baseline | T | Tampering | Trend-Manipulation durch editierte Baseline | Keine Integritätsprüfung | **Niedrig** — User-lokale Datei |
| DS-3 Telemetrie | I | Info Disclosure | JSONL enthält Analyse-Metadaten | Opt-in; Redaction-Keys | **Niedrig** |

---

## 4. Residual Risk Summary

| ID | Bedrohung | Residual Risk | Begründung | FTA-Kandidat |
|----|-----------|---------------|------------|--------------|
| **S-TB4-01** | Gefälschte AI-Attribution via Co-author-Headers | **Mittel** | Heuristik-basiert; keine kryptographische Verifizierung möglich | Nein (Design-Entscheidung) |
| **T-TB2-01** | Config deaktiviert kritische Signale | **Mittel** | Valides Feature; aber in PR-Kontext ausnutzbar | Nein (Warnung genügt) |
| **T-TB2-03** | BOM in pyproject.toml bricht Analyse ab | **Offen** ⚠️ | Bekannter Bug, unfixed | **Ja → FTA FT-3** |
| **I-TB5-01** | related_files leaken Pfade außerhalb target-path | **Offen** ⚠️ | Kein Filter implementiert | **Ja → Risk Register** |
| **R-TB4-01** | AI-Attribution absichtlich verschleierbar | **Mittel** | Heuristik-Limitation; in Docs dokumentieren | Nein |
| **S-TB2-01** | Config-Injection via Fork/PR | **Mittel** | PR-Review ist einzige Kontrolle | Nein (Warnung genügt) |

---

## 5. Empfohlene Maßnahmen (priorisiert)

| Prio | Maßnahme | Bedrohung | Aufwand | Impact |
|------|----------|-----------|---------|--------|
| 1 | BOM-Strip in Config-Loader implementieren | T-TB2-03 | Niedrig | Beseitigt First-Run-Blocker |
| 2 | Related-files auf target-path filtern | I-TB5-01 | Niedrig | Schließt Info-Disclosure-Lücke |
| 3 | Warnung wenn >50% Core-Signale via Config deaktiviert | T-TB2-01 | Niedrig | Reduziert absichtliche Blind-Spot-Erzeugung |
| 4 | AI-Attribution als „heuristisch" markieren + Confidence | S-TB4-01 | Mittel | Transparenz über Limitations |
| 5 | `--no-repo-config` CLI-Option | S-TB2-01 | Niedrig | Sicherer CI-Betrieb auf Forks |

---

## Review-Trigger

- **Neuer Input-Pfad** (z.B. neues Config-Format, neuer API-Endpoint): STRIDE-Element Pflicht
- **Neuer Output-Kanal**: Information-Disclosure-Prüfung Pflicht
- **Architekturänderung** (z.B. Netzwerk-Feature, Remote-Scan): vollständiger STRIDE-Refresh
- **Security-Advisory**: betroffene Trust Boundary neu bewerten

---
id: ADR-044
status: proposed
date: 2026-04-10
supersedes:
---

# ADR-044: Architecture Boundary Presets

## Kontext

Drift erkennt Layer-Verletzungen über das AVS-Signal (Architecture Violation Signal), das auf vom Benutzer konfigurierten `policies.layer_boundaries` in `drift.yaml` basiert. Aktuell muss jeder Benutzer diese Boundaries manuell definieren — ein hoher Einstiegshürde, die die Einführbarkeit reduziert (Policy §6, Stufe 5).

Wettbewerbsanalyse (KW 15/2026) zeigt, dass vergleichbare Tools (ArchUnit, Dependency-Cruiser) vordefinierte Architektur-Templates bieten, was die Time-to-Value erheblich verkürzt.

## Entscheidung

**Was wird getan:**

1. Vordefinierte Boundary-Sets als YAML-Presets unter `src/drift/presets/` einführen:
   - `layered.yaml` — Klassische 3-Schicht: `api → service → data`; upward imports verboten
   - `hexagonal.yaml` — Ports & Adapters: `domain` darf nicht von `infra`/`adapters` importieren
   - `modular_monolith.yaml` — Module kommunizieren nur über explizite Public APIs
   - `feature_sliced.yaml` — Feature-Slices mit strikter Isolation (Cross-Feature-Imports verboten)

2. `drift init --preset <name>` erweitern: Lädt das gewählte Preset und injiziert die Boundaries in die generierte `drift.yaml`

3. Config-Loader erweitern: `DriftConfig.from_preset(name)` als Factory-Methode

4. Optional: Interaktiver Modus bei `drift init`, der anhand erkannter Verzeichnisstruktur ein Preset vorschlägt

**Was explizit nicht getan wird:**

- Keine automatische Preset-Erkennung bei `drift analyze` (nur bei `drift init`)
- Keine Runtime-Überschreibung von Presets — Preset wird einmalig in `drift.yaml` materialisiert
- Keine Custom-Preset-API für Plugins (Phase D)
- Kein Merge von Preset + bestehender User-Config — Preset schreibt neue Datei

## Begründung

**Gewählt: Materialisierte Presets (Preset → drift.yaml)**

- Benutzer behalten volle Kontrolle über die generierte Config
- Keine versteckte Magie — die Boundaries sind direkt in `drift.yaml` sichtbar und editierbar
- Presets sind nur ein Startpunkt, kein Lock-in
- Einfacher zu debuggen als dynamisch geladene, mergbare Konfigurationen

**Verworfen: Dynamische Preset-Vererbung (`extends: layered`)**

- Erhöht Komplexität des Config-Loaders erheblich
- Merge-Semantik (User-Override vs. Preset-Default) ist fehleranfällig
- Versteckt die effektiven Boundaries vor dem Benutzer
- Widerspricht Drift-Policy (Unsicherheitsreduktion > Komplexität)

**Verworfen: Nur Dokumentation (Copy-Paste-Beispiele)**

- Keine Integration in den Workflow
- Höhere Fehlerquote durch manuelle Übertragung

## Konsequenzen

1. **Positiv:** Einführbarkeit verbessert sich — neue Benutzer können AVS-Signal sofort nutzen
2. **Positiv:** Verständlichkeit steigt — Presets dokumentieren gängige Architekturmuster
3. **Risiko:** Zu generische Presets erzeugen FP-Flut bei Repos, die nicht exakt dem Muster entsprechen → Mitigation: Presets müssen mit realen Repos empirisch validiert werden
4. **Risiko:** Falsche Verzeichnis-Mappings (z.B. `src/api/` vs. `api/`) → Mitigation: Presets verwenden Glob-Patterns, nicht exakte Pfade
5. **Trade-off:** Einmalige Materialisierung bedeutet, dass Preset-Updates bestehende `drift.yaml` nicht automatisch aktualisieren

## Validierung

1. **Empirische Validierung:** Jedes Preset gegen mindestens 3 reale Open-Source-Repos testen, die das jeweilige Architekturmuster verwenden
2. **Precision-Test:** FP-Rate beim Preset-geführten AVS-Signal ≤ 15% auf den Validierungs-Repos
3. **Lernzyklus (§10):** 4 Wochen nach Release prüfen:
   - Adoption-Rate (wie viele `drift init --preset` vs. manuell?)
   - FP-Rate in Issues/Feedback
   - Ergebnis: bestätigt | widerlegt | unklar | zurückgestellt

### Referenzierte Artefakte

- `src/drift/commands/init_cmd.py` — `--preset` Flag
- `src/drift/config.py` — `DriftConfig.from_preset()`
- `src/drift/presets/` — Preset-YAML-Dateien
- `tests/` — Preset-Integrationstests
- `audit_results/fmea_matrix.md` — Preset-bezogene FP-Risiken (bei Implementierung)
- `benchmark_results/` — Feature-Evidence mit Preset-Validierung

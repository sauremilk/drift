---
id: ADR-039
status: proposed
date: 2026-04-10
supersedes:
---

# ADR-039: Scoring-Aktivierung von MAZ, PHR, HSC, ISD, FOE

## Kontext

Drift v2.8.0 enthält 9 report-only-Signale (Gewicht 0.0), die zwar Findings erzeugen, aber nicht in den Composite-Score einfließen. Fünf dieser Signale adressieren direkt Fehlermuster, die bei KI-generiertem Code besonders häufig auftreten:

- **MAZ** (Missing Authorization, CWE-862): KI-Coder erzeugen funktionale Endpoints ohne Zugriffskontrolle.
- **PHR** (Phantom Reference): KI-Modelle halluzinieren Funktions-/Klassenreferenzen, die im Projekt nicht existieren.
- **HSC** (Hardcoded Secret, CWE-798): KI-Assistenten übernehmen Platzhalter-Credentials aus Trainingsdaten.
- **ISD** (Insecure Default, CWE-1188): KI schlägt unsichere Voreinstellungen vor (TLS off, Debug an).
- **FOE** (Fan-Out Explosion): KI-generierter Code importiert übermäßig viele externe Bibliotheken (Supply-Chain-Risiko).

Durch Aktivierung dieser Signale für das Scoring wird Drift zu einem effektiveren Tool für Agent-Workflows, die AI-generierten Code prüfen.

**Voraussetzung**: PHR fehlt derzeit in `signal_mapping.py` (Bug) — wird im gleichen Commit behoben.

## Entscheidung

**Wird getan:**
1. PHR-Abbreviation in `signal_mapping.py` registrieren
2. Gewichte für 5 Signale von 0.0 auf konservative Werte setzen:
   - `missing_authorization: 0.02`
   - `phantom_reference: 0.02`
   - `hardcoded_secret: 0.01`
   - `insecure_default: 0.01`
   - `fan_out_explosion: 0.005`
3. Gesamt-Gewichts-Delta: +0.065 (von ~0.905 auf ~0.97)
4. Fehlende ISD-Ground-Truth-Fixtures ergänzen
5. Audit-Artefakte gemäß Policy §18 aktualisieren

**Wird explizit nicht getan:**
- Keine Aktivierung von TSA, CXS, CIR, DCA (niedrigere Agent-Relevanz)
- Keine Aktivierung von TVS (report-only aus anderen Gründen, nicht Gegenstand dieses ADR)
- Keine Änderung der Signal-Heuristiken selbst
- Keine Gewichte über 0.02 (konservativer Rollout, anhebbar nach weiterer Validierung)

## Begründung

**Warum diese 5 Signale:**
Die Auswahl basiert auf der Literatur zu AI-Coding-Risiken. Mehrere Studien belegen, dass AI-generierter Code typischerweise unter fehlender Authentifizierung, halluzierten Referenzen, unsicheren Defaults und vergessenen Geheimnissen leidet. Diese 5 Signale bilden die häufigsten AI-spezifischen Fehlerklassen ab.

**Warum diese Gewichte:**
- MAZ und PHR erhalten 0.02 (höchster Wert), da beide direkte Sicherheits- bzw. Korrektheitsprobleme abdecken.
- HSC und ISD erhalten 0.01, da sie spezifischere Muster erkennen und weniger breit wirken.
- FOE erhält 0.005, da Supply-Chain-Risiko mittelbarer ist als direkte Sicherheitslücken.
- Alle Gewichte sind bewusst niedrig gehalten, um den Composite-Score nicht zu destabilisieren.

**Verworfene Alternativen:**
- Höhere Gewichte (0.05+): Zu riskant ohne breitere Validierung auf externen Repos
- Gleichzeitige Aktivierung aller 9 report-only: TSA/CXS/CIR/DCA sind nicht AI-spezifisch und haben niedrigere Dringlichkeit
- Keine Aktivierung: Verschenkt Wert für den wachsenden Agent-Use-Case

## Konsequenzen

- Composite-Score aller Repos steigt marginal (~1-3% je nach Codebase)
- Agent-Workflows erhalten automatisch Feedback zu AI-typischen Fehlermustern
- 20 Signale werden scoring-aktiv (statt bisher 15+3 nach TVS-Deaktivierung)
- Bei unerwartet hoher FP-Rate auf externen Repos können Gewichte einzeln auf 0.0 zurückgesetzt werden

## Validierung

Erfolgskriterien (Policy §10):
1. `pytest tests/test_precision_recall.py -v` — alle 5 Signale bestehen mit P≥0.95
2. `python scripts/_mutation_benchmark.py` — kein Recall-Regression auf bestehenden Signalen
3. Selbstanalyse (`drift analyze --repo . --exit-zero`) zeigt stabile Scores ohne neue FP in `src/drift/`
4. Feature-Evidence generiert: `benchmark_results/v2.9.0_signal_activation_feature_evidence.json`

Lernzyklus-Ergebnis: bestätigt, wenn P≥0.95 auf den 5 Signalen über 3+ externe Repos gehalten wird. Widerlegt, wenn FP-Rate auf realen Repos deutlich über 10% liegt — dann Gewichte zurücknehmen.

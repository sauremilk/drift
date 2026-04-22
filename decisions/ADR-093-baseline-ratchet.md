# ADR-093 — Proaktives Baseline-Management (Baseline Ratchet)

- Status: proposed
- Date: 2026-05-04
- Paket: 2A (Plan "QA 2026")
- Abhaengig von: ADR-089 (Severity-Gate im Agent-Prompt), ADR-090 (Agent-Telemetry)

## Kontext

`drift baseline save` persistiert die aktuelle Finding-Menge als Fingerprint-Set.
Die bisherige Adoptionspraxis war:

1. Entwickler fuehrt `drift baseline save` aus.
2. Spaeter `drift check --diff` oder `drift baseline diff` rein **informativ**.
3. Ein Pre-Commit-Gate, das **neue Findings blockiert**, existierte nicht.
4. Ein Agent oder Entwickler konnte die Baseline jederzeit mit einem weiteren
   `baseline save` unbemerkt "weiterratschen". Drift-Erosion blieb stumm,
   obwohl das Tool sie genau verhindern soll.

Das widerspricht Paket 2A im Plan `QA 2026`: Baseline-Drift muss **vor dem
Commit** erkannt und ein Baseline-Update muss ein **expliziter, reviewbarer
Akt** sein.

## Entscheidung

Zwei additive CLI-Kontrakte plus ein Pre-Commit-Hook:

1. **`drift baseline diff --fail-on-new N`**
   Nicht-mutierender Exit-Code-Kontrakt:
   `exit 1`, wenn `len(new_findings) > N`.
   Default unveraendert (None = kein Gate, rueckwaertskompatibel).
   Damit kann das bestehende `baseline diff` als Pre-Commit-Gate verwendet
   werden, ohne dass ein zweiter Code-Pfad noetig ist.

2. **`drift baseline update --confirm`**
   Deliberate Alias fuer `baseline save`, der **ohne** `--confirm` mit
   `exit 2` abbricht. Damit kann ein Agent (oder ein Entwickler per
   Shell-History) die Baseline nicht stillschweigend ratschen.
   `baseline save` bleibt unveraendert (Backwards-Compat fuer bestehende
   CI-Skripte und den initialen Baseline-Aufbau).

3. **Pre-Commit-Hook `drift-baseline-check`** in `.pre-commit-hooks.yaml`
   ruft `drift baseline diff --fail-on-new 0` auf. Standardmaessig
   blockiert jede zusaetzliche Drift seit der letzten Baseline. Projekte,
   die eine Toleranz brauchen, setzen `args: [--fail-on-new, "3"]` o. ae.

### Nicht-Ziele

- **Kein Auto-Update.** Die Baseline wird nie automatisch geschrieben.
- **Keine Threshold-Logik auf Score-Basis.** Der ursprueng geplante
  `baseline.ratchet_threshold` in `drift.yaml` bleibt bewusst weg: die
  Anzahl NEUER Findings ist das direkt operationalisierbare Signal. Ein
  Score-Threshold ist anfaellig fuer Rebalancing der Gewichte und
  erzeugt Falsch-Positive bei legitimen Refactors.
- **Kein CHANGELOG-Auto-Eintrag** beim `update`. Policy §13 verlangt,
  dass Baseline-Updates ein erklaerender Commit-Body begleitet —
  automatisches Anhaengen an CHANGELOG erzeugt Lärm statt Erklaerung.

## Konsequenzen

### Positiv

- Baseline-Drift ist nicht mehr stumm.
- Der bestehende `baseline diff`-Code wird wiederverwendet; keine neue
  Parallel-Logik, keine neue Fehlerquelle.
- Pre-Commit-Integration ist ein Einzeiler fuer Anwender.
- Agent-Vertraege (Paket 1A, Severity-Gate) koennen jetzt `BLOCK` auf
  "neue Findings ueberschreiten Threshold" stuetzen, ohne selbst zu
  messen.

### Trade-offs

- `drift baseline update` ist semantisch nahe an `baseline save`. Das
  erzeugt oberflaechliche Redundanz. Bewusst akzeptiert, weil die
  Semantik unterschiedlich ist: `save` = erstmalige oder CI-seitige
  Erzeugung, `update` = bewusstes Anheben einer bestehenden Baseline.
- Pre-Commit-Hook kann Entwickler frustrieren, wenn sie gerade einen
  unvermeidbar driftigen Refactor machen. Mitigation: `SKIP=drift-baseline-check`
  ist der dokumentierte Eskalationspfad (standard pre-commit-Verhalten).

## Validierung

1. `tests/test_baseline.py::TestBaselineRatchetADR093` (5 Tests, alle gruen):
   - diff `--fail-on-new 0` passt bei sauberem Stand.
   - diff `--fail-on-new 0` liefert `exit 1` bei neuer Drift.
   - diff `--fail-on-new N` respektiert den Threshold.
   - update ohne `--confirm` liefert `exit 2`.
   - update `--confirm` schreibt eine gueltige Baseline-Datei.
2. `.pre-commit-hooks.yaml` hat einen neuen `drift-baseline-check` Eintrag.
3. Bestehende Tests (`tests/test_baseline.py`) bleiben unveraendert gruen.

## Risiken

Dokumentiert in `audit_results/risk_register.md` als
`RISK-ADR-093-BASELINE-RATCHET`. Hauptrisiko: Falsch-Positive beim
legitimen Refactor, mitigiert durch `SKIP=...` Eskalation und explizites
`drift baseline update --confirm`.

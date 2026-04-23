---
id: ADR-016
status: proposed
date: 2026-04-07
supersedes:
---

# ADR-016: Security-Signale Wave-2 Kalibrierung (MAZ/ISD/HSC)

## Kontext

Nach ADR-015 sind MAZ, ISD und HSC funktional stabil, jedoch verbleiben
praxisnahe Praezisions- und Recall-Luecken:

- MAZ fallback erkennt auth-nahe Parameter nur bei exaktem String-Match.
- ISD akzeptiert aktuell jede Substring-Variante von `drift:ignore-security`
  in den ersten Zeilen und kann dadurch unbeabsichtigt vollstaendig
  unterdrueckt werden.
- HSC erkennt bekannte Prefix-Secrets nicht, wenn sie in ueblichen
  Wrapper-Formen wie `Bearer sk-...` auftreten.

## Entscheidung

Wir fuehren eine zweite, eng begrenzte Kalibrierungswelle durch:

1. MAZ: auth-parameter Normalisierung erweitern (camelCase + konservative
   Muster fuer token/claims/credentials/principal), weiterhin nur im
   decorator-fallback Pfad.
2. ISD: `drift:ignore-security` nur noch ueber explizite Kommentar-Direktive
   (Wortgrenze) auswerten; keine zufaelligen Substring-Treffer.
3. HSC: Prefix-Pruefung um gaengige Wrapper normalisieren (`Bearer ...`,
   `token ...`), ohne bekannte Safe-Value-Ausnahmen zu lockern.

## Begruendung

Die Aenderungen folgen Drift-Priorisierung:

- Glaubwuerdigkeit und Signalpraezision vor Feature-Ausbau.
- Kleine, testgetriebene Heuristik-Schaerfungen mit klaren TP/TN-Regressionen.

## Konsequenzen

- Erwartet: bessere Security-Actionability in realen API-/HTTP-Kontexten.
- Trade-off: MAZ kann in seltenen Namenskonventionen auth-indikative Parameter
  staerker als Kontextsignal interpretieren.
- Trade-off: ISD Ignore-Direktive wird strenger; versehentliche Skip-Muster
  greifen nicht mehr.

## Validierung

- `python -m pytest tests/test_missing_authorization.py -q --maxfail=1`
- `python -m pytest tests/test_insecure_default.py -q --maxfail=1`
- `python -m pytest tests/test_hardcoded_secret.py -q --maxfail=1`
- `python -m pytest tests/test_precision_recall.py::test_precision_recall_report -q -s`

Erfolgsbedingung:

- neue MAZ/ISD/HSC-Regressionsfaelle sind gruen,
- bestehende Security-Fixtures behalten gruenen P/R-Status,
- keine neuen Fehler in geaenderten Dateien.

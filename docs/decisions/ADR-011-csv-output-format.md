---
id: ADR-011
status: proposed
date: 2026-04-03
supersedes:
---

# ADR-011: CSV-Ausgabeformat fuer Findings

## Kontext

Drift bietet derzeit rich-, json-, sarif-, agent-tasks- und github-Ausgaben.
Fuer viele Teams fehlt ein leicht importierbares Tabellenformat fuer schnelle
Weiterverarbeitung in Kalkulation, einfache Filter-Pipelines oder PM-Boards.

## Entscheidung

Wir fuehren ein neues Output-Format `csv` fuer `drift analyze` und `drift check`
ein. Die Ausgabe enthaelt pro Finding genau eine Zeile mit stabilem Header:

`signal,severity,score,title,file,start_line,end_line`

Rahmenbedingungen:

- Implementierung in `src/drift/output/csv_output.py`.
- Nutzung des Python-Standardmoduls `csv` (keine neue Abhaengigkeit).
- Deterministische Zeilenreihenfolge analog zu bestehenden
  maschinenlesbaren Ausgaben.
- Keine Aenderung an Signalberechnung, Scoring oder Severity-Logik.

Explizit nicht Teil dieser ADR:

- keine neuen Felder im CSV-Schema in dieser Iteration
- keine Aenderung an `self`/`scan`-Format-Optionen

## Begründung

CSV verbessert Einfuehrbarkeit und Handlungsfaehigkeit bei minimaler
Komplexitaet: einfacher Datenaustausch ohne Schema-Parser, reproduzierbar und
 mit bestehender CLI-Ausgabe konsistent.

## Konsequenzen

- Additiver CLI-Output-Kanal ohne Breaking Change.
- Zusätzlicher Pflegeaufwand fuer einen weiteren Serializer (niedrig).
- CSV bleibt bewusst kompakt; tiefe Metadaten bleiben in JSON/SARIF.

## Validierung

- Unit-Tests fuer Header, Feldreihenfolge und CSV-Escaping.
- CLI-Choice-Test fuer `--output-format csv`.
- Policy §10 Lernzyklus-Status: unklar (Nutzerfeedback nach Feldnutzung).

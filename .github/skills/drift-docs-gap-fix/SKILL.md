---
name: drift-docs-gap-fix
description: "Minimaler Workflow zum Finden und Schliessen konkreter Dokumentationsluecken im Drift-Repo. Verwenden, wenn neue externe Nutzer an docs, docs-site oder Onboarding-Inhalten scheitern, nach Releases Dokumentation nachgezogen werden muss oder vor Outreach die oeffentlichen Wege auf Vollstaendigkeit geprueft werden sollen. Nicht fuer grosse Umstrukturierungen, IA-Redesigns oder neue Dokumentationsstrategien verwenden."
argument-hint: "Beschreibe die Verwirrung oder Frage, den betroffenen Nutzerpfad und ob es um docs/ oder die veroeffentlichte Doku in docs-site/ geht."
---

# Drift Docs Gap Fix

Verwende diese Skill, um eine konkrete Dokumentationsluecke mit dem kleinstmoeglichen, repo-konformen Patch zu schliessen.

Ziel ist nicht, die Doku neu zu strukturieren, sondern genau die fehlende oder veraltete Information an der richtigen Stelle zu ergaenzen.

## Verwenden Wenn

- ein externer Nutzer eine Frage stellt, die in der Dokumentation beantwortet sein sollte
- nach einem Release geprueft werden soll, ob neue Funktionen dokumentiert sind
- vor Outreach oder Onboarding die wichtigsten Nutzerpfade auf Luecken geprueft werden sollen
- bestehende Doku sichtbar veraltet, unvollstaendig oder missverstaendlich ist

## Nicht Verwenden

- fuer neue Informationsarchitektur, grosse Umbauten oder Rewrites ganzer Seiten
- fuer Marketing- oder Brand-Texte ohne konkreten Dokumentationsmangel
- fuer Aenderungen ohne nachweisbare Nutzerverwirrung, Release-Aenderung oder Informationsluecke
- fuer neue Top-Level-Seiten, solange eine praezise bestehende Zielseite vorhanden ist

## Gap-Typen

Ordne den Fall zuerst einem konkreten Gap-Typ zu:

| Gap-Typ | Bedeutung |
|---|---|
| Fehlend | Das Thema existiert im Produkt oder Code, aber nicht in der Doku |
| Veraltet | Die Doku beschreibt altes Verhalten oder alte Kommandos |
| Kein Beispiel | Das Konzept wird genannt, aber ohne brauchbares Beispiel |
| Falsche Annahme | Die Doku setzt Kontext voraus, den neue Nutzer nicht haben |

Wenn kein Gap-Typ sauber passt, ist der Fall meist zu unscharf fuer einen Minimal-Patch und muss erst genauer eingegrenzt werden.

## Standard-Workflow

### 1. Luecke exakt formulieren

Halte die konkrete Verwirrung in einem Satz fest:

- Was wollte der Nutzer erreichen?
- Was hat in der Doku gefehlt oder irritiert?
- Welcher Gap-Typ liegt vor?

Ohne diese Formulierung keine Patch-Arbeit beginnen.

### 2. Die richtige Doku-Oberflaeche bestimmen

Pruefe zuerst, ob die Luecke in `docs/` oder in `docs-site/` liegt. Beide Bereiche sind gleichrangig; die richtige Flaeche ergibt sich aus dem Nutzerpfad und dem Dokumentationstyp.

- `docs-site/` ist die veroeffentlichte MkDocs-Dokumentation; nutze `mkdocs.yml` als Navigationsindex
- `docs/` enthaelt repo-interne oder begleitende Dokumente; dort gilt die lokale Ordnerstruktur, nicht automatisch die MkDocs-Navigation

Wenn unklar ist, ob der Nutzer eine oeffentliche Produktseite oder ein internes Maintainer-Dokument braucht, klaere das zuerst statt blind in `docs/` zu patchen.

### 3. Zielseite lokalisieren

Bevorzuge immer die spezifischste existierende Datei.

- Bei `docs-site/`: nutze `mkdocs.yml`, um die naechste passende Seite zu finden
- Bei `docs/`: suche die fachlich engste bestehende Datei statt eine neue Seite anzulegen
- Neue Dateien oder neue Top-Level-Navigation nur dann, wenn nachweislich keine passende bestehende Seite existiert

### 4. Minimalen Patch schreiben

Der Patch muss nur die identifizierte Luecke schliessen.

Pflicht-Constraints:

- kein Scope Creep
- keine neue Begriffswelt ohne Not
- keine neue Top-Level-Struktur ohne vorherige Pruefung der Navigation
- Beispiele muessen ausfuehrbar oder direkt pruefbar sein, kein Pseudocode
- Ton, Ueberschriften und Detailtiefe muessen zur Zielseite passen

### 5. Gegenpruefen

Vor Abschluss kontrollieren:

- beantwortet der Patch genau die urspruengliche Verwirrung?
- ist die Information an der ersten plausiblen Suchstelle gelandet?
- erzeugt der Patch keine zweite Quelle fuer dieselbe Regel?
- ist das Beispiel korrekt und aktuell?

Wenn eine dieser Fragen mit Nein beantwortet wird, Patch nachschaerfen oder Zielseite neu waehlen.

### 6. Ergebnis ausgeben

Liefere das Ergebnis in der direkt nuetzlichsten Form:

- aendere die konkrete Datei direkt, wenn Zielstelle und Inhalt eindeutig sind
- liefere andernfalls einen Patch gegen die konkrete Datei
- nutze einen klar abgegrenzten Ersatzblock nur dann, wenn ein Patch technisch unpraktisch waere

Nenne immer:

- die betroffene Datei
- warum genau diese Datei die richtige Stelle ist
- welche konkrete Nutzerverwirrung geschlossen wurde

## Entscheidungsregeln

- Wenn mehrere Dateien moeglich wirken, gewinnt die Datei, die der Nutzer mit der hoechsten Wahrscheinlichkeit zuerst oeffnet.
- Wenn die Aenderung ein neues Konzept einfuehren wuerde, ist sie kein Docs-Gap-Fix mehr, sondern ein groesserer Docs-Entscheid.
- Wenn dieselbe Information bereits an anderer Stelle steht, ergaenze bevorzugt Querverweis oder Praezisierung statt Doppelung.
- Wenn die Doku korrekt ist, aber schlecht auffindbar, pruefe erst Navigations- oder Link-Fix statt Textausbau.

## Antwortmuster

Antworte in dieser Reihenfolge:

1. beschriebene Nutzerverwirrung in einem Satz
2. Gap-Typ
3. gewaehlte Zieldatei mit kurzer Begruendung
4. minimaler Patch
5. kurze Gegenpruefung, warum der Patch die Luecke schliesst

## Guardrails

- Keine grossen Doku-Umbauten unter dem Deckmantel eines kleinen Gaps
- Keine neuen Seiten aus Bequemlichkeit
- Keine Beispiele, die nicht zur aktuellen CLI oder zum aktuellen Verhalten passen
- Keine Navigation aendern, ohne die Auswirkung auf `mkdocs.yml` oder bestehende Docs-Pfade zu pruefen

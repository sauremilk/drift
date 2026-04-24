# Drift — Policy für Produkt, Priorisierung und Arbeitsweise

## 1. Zweck

1.1 Drift ist ein statischer Analyzer zur Erkennung architektonischer Kohärenzprobleme in Codebasen.

1.2 Zweck von Drift ist es, strukturelle Erosion in einer Codebase zu erkennen, zu benennen, zu priorisieren und über Zeit vergleichbar zu machen.

1.3 Drift darf nur solche Ergebnisse erzeugen, die technisch nachvollziehbar, reproduzierbar und für eine konkrete Handlung verwertbar sind.

## 2. Geltungsbereich

2.1 Diese Policy gilt für sämtliche Produktentscheidungen, technische Entscheidungen, Priorisierungsentscheidungen, Analyseentscheidungen und Roadmap-Entscheidungen im Zusammenhang mit Drift.

2.2 Diese Policy gilt unabhängig davon, ob bereits Kunden, Pilotanwender oder andere externe Nutzer vorhanden sind.

2.3 Diese Policy hat Vorrang vor informellen Annahmen, spontanen Ideen und nicht dokumentierten Einzelentscheidungen.

## 3. Grundsatz

3.1 Drift wird nicht nach dem Kriterium „möglichst viele Features“ entwickelt.

3.2 Drift wird nach dem Kriterium entwickelt, ob eine Funktion die Qualität der Analyse, die Glaubwürdigkeit der Ergebnisse, die Verständlichkeit der Befunde oder die Vergleichbarkeit über Zeit verbessert.

3.3 Jede Entwicklung muss mindestens einem in dieser Policy definierten Zweck dienen.

## 4. Produktziel

4.1 Das Produktziel von Drift ist die messbare Erkennung von architektonischer Drift und Codebase-Erosion.

4.2 Drift soll insbesondere folgende Problemklassen erfassen:
- Pattern Fragmentation
- Architecture Violations
- Mutant Duplicates
- Explainability Deficit
- Trendabweichungen über Zeit
- unklare oder nicht handlungsfähige Befunde

4.3 Drift darf keine Ergebnisse priorisieren, die keinen realen Zusammenhang mit struktureller Kohärenz besitzen.

## 5. Definitionen

5.1 **Signalqualität** bezeichnet die Fähigkeit eines Befunds, ein reales Problem korrekt zu beschreiben.

5.2 **Glaubwürdigkeit** bezeichnet das Ausmaß, in dem ein Nutzer das Ergebnis ohne zusätzlichen Interpretationsaufwand als belastbar einordnen kann.

5.3 **Handlungsfähigkeit** bezeichnet das Ausmaß, in dem ein Befund eine konkrete nächste Maßnahme ermöglicht.

5.4 **Trendfähigkeit** bezeichnet die Fähigkeit, Ergebnisse über mehrere Läufe hinweg vergleichbar zu machen.

5.5 **Einführbarkeit** bezeichnet das Ausmaß, in dem Drift ohne unnötige Reibung in reale Workflows integriert werden kann.

## 6. Priorisierungsregel

6.1 Neue Arbeit wird ausschließlich nach Risiko, Wirkung und Aufwand priorisiert.

6.2 Die Priorisierung erfolgt nach folgender Formel:

**Priorität = (Unsicherheit × Schaden × Nutzbarkeit) / Aufwand**

6.3 Die Variablen sind wie folgt zu verstehen:
- **Unsicherheit** = Grad der Ungewissheit über den tatsächlichen Nutzen oder die Richtigkeit einer Annahme
- **Schaden** = Ausmaß des negativen Effekts, falls eine Annahme falsch ist
- **Nutzbarkeit** = unmittelbarer Nutzen einer Änderung für die Anwendung von Drift
- **Aufwand** = technischer und organisatorischer Implementierungsaufwand

6.4 Eine Aufgabe mit hohem Aufwand und geringer Wirkung ist nachrangig.

6.5 Eine Aufgabe mit hoher Unsicherheit und hohem Schadenspotenzial ist vorrangig zu behandeln.

## 7. Prioritätsreihenfolge

7.1 Bei konkurrierenden Vorhaben gilt folgende feste Reihenfolge:

1. Erhaltung der Glaubwürdigkeit von Drift
2. Verbesserung der Präzision der Signale
3. Verbesserung der Verständlichkeit der Befunde
4. Reduktion von False Positives und False Negatives
5. Verbesserung der Einführbarkeit
6. Verbesserung der Trendanalyse
7. Erweiterung um zusätzliche Funktionen, Formate oder Komfortmerkmale

7.2 Eine niedrigere Prioritätsstufe darf eine höhere Prioritätsstufe nicht verdrängen.

## 8. Zulassungskriterien für Arbeit

8.1 Eine Aufgabe darf nur begonnen werden, wenn sie mindestens eines der folgenden Kriterien erfüllt:
- sie reduziert eine zentrale Unsicherheit
- sie verbessert die Signalqualität
- sie erhöht die Glaubwürdigkeit
- sie erhöht die Handlungsfähigkeit
- sie verbessert die Trendfähigkeit
- sie erleichtert die Einführbarkeit

8.2 Eine Aufgabe, die keines dieser Kriterien erfüllt, darf nicht priorisiert werden.

## 9. Ausschlusskriterien

9.1 Eine Aufgabe ist zurückzustellen, wenn sie ausschließlich eines der folgenden Ergebnisse erzeugt:
- mehr Ausgabe ohne besseren Erkenntniswert
- mehr Komplexität ohne klaren Nutzen
- mehr Oberfläche ohne bessere Analyse
- mehr Analyse ohne Validierung des Ergebnisses
- mehr technische Ausarbeitung ohne Beitrag zur Produktwirkung

9.2 Eine Aufgabe ist ebenfalls zurückzustellen, wenn ihr Nutzen nicht eindeutig benennbar ist.

## 10. Arbeitsmodus

10.1 Drift wird in kurzen Lernzyklen entwickelt.

10.2 Jeder Zyklus muss genau ein vorrangiges Erkenntnisziel haben.

10.3 Ein Zyklus darf nur eine der folgenden Zielarten besitzen:
- Validierung einer Annahme
- Reduktion einer Unsicherheit
- Verbesserung eines Signals
- Prüfung einer Produktentscheidung

10.4 Jeder Zyklus endet mit einem dokumentierten Ergebnis.

10.5 Zulässige Zyklus-Ergebnisse sind ausschließlich:
- bestätigt
- widerlegt
- unklar
- zurückgestellt

## 11. Entscheidungsregeln ohne Kundenfeedback

11.1 Sofern kein externes Kundenfeedback vorliegt, werden Prioritäten nicht nach Wunsch, sondern nach Risiko gesetzt.

11.2 Die führende Entscheidungsfrage lautet:

**Welche Annahme gefährdet das Projekt am stärksten, falls sie falsch ist?**

11.3 Die Arbeit, die diese Annahme am schnellsten überprüft, ist vorrangig zu behandeln.

11.4 Hypothesen, die keine prüfbare Folgehandlung ermöglichen, sind nicht priorisierbar.

## 12. Validierungsstrategie

12.1 Solange keine belastbaren Kundendaten vorliegen, gelten folgende Validierungsquellen:
- eigene Nutzung
- Analyse realer Repositories
- manuelle Gegenprüfung
- wiederholte Läufe über Zeit
- Beobachtung reproduzierbarer Ergebnisse
- Vergleich zwischen Befund und tatsächlicher Codebasis

12.2 Ein Ergebnis gilt nur dann als valide, wenn es reproduzierbar ist.

12.3 Ein Ergebnis gilt nur dann als verwertbar, wenn daraus eine konkrete Entscheidung abgeleitet werden kann.

## 13. Qualitätsanforderungen

13.1 Jeder Befund muss mindestens die folgenden Eigenschaften besitzen:
- technische Nachvollziehbarkeit
- Reproduzierbarkeit
- eindeutige Zuordnung zu einer Ursache
- klare Benennung der betroffenen Stelle
- nachvollziehbare Begründung
- erkennbare nächste Maßnahme

13.2 Ein Befund ohne klare Begründung ist unzulässig.

13.3 Ein Befund ohne mögliche nächste Maßnahme ist unvollständig.

## 14. Roadmap-Hierarchie

14.1 Die Roadmap ist in der folgenden Reihenfolge zu behandeln:

### Phase 1 — Vertrauen
- Ergebnisse müssen nachvollziehbar sein
- Ergebnisse müssen reproduzierbar sein
- Fehlalarme müssen reduziert werden
- Befunde müssen eindeutig erklärbar sein

### Phase 2 — Relevanz
- Signale müssen reale architektonische Probleme abbilden
- Empfehlungen müssen präzise sein
- Prioritäten müssen sachlich begründet sein

### Phase 3 — Einführbarkeit
- Integration in CI muss möglich sein
- Integration in lokale Workflows muss möglich sein
- Konfiguration muss eindeutig sein
- Bedienung muss ohne unnötige Reibung möglich sein

### Phase 4 — Skalierung
- größere Codebasen müssen unterstützt werden
- mehrere Sprachen dürfen ergänzt werden
- Trendanalyse muss erweitert werden
- Auswertung muss robuster werden

14.2 Phase 4 darf Phase 1 nicht verdrängen.

14.3 Eine Skalierungsmaßnahme ohne gesichertes Vertrauen ist nachrangig.

## 15. Regel für neue Features

15.1 Ein neues Feature darf nur eingeführt werden, wenn es mindestens einen der folgenden Punkte verbessert:
- Signalqualität
- Glaubwürdigkeit
- Handlungsfähigkeit
- Einführbarkeit
- Trendfähigkeit

15.2 Ein Feature ist unzulässig, wenn es nur zusätzlichen Umfang erzeugt.

15.3 Ein Feature ist unzulässig, wenn sein Beitrag nicht klar benennbar ist.

15.4 Ein Feature ist unzulässig, wenn es ein bestehendes Problem verdeckt, statt es zu verbessern.

## 16. Umgang mit unklaren Entscheidungen

16.1 Bei unklarer Entscheidungslage ist diejenige Option zu wählen, die die größte Unsicherheit reduziert.

16.2 Sind mehrere Optionen möglich, ist diejenige Option zu wählen, die den höchsten Erkenntniswert pro Aufwandseinheit besitzt.

16.3 Ist keine Option hinreichend begründet, ist keine Umsetzung vorzunehmen.

## 17. Nicht verhandelbare Anforderungen

17.1 Drift darf nicht zu einem Werkzeug werden, das lediglich Probleme auflistet.

17.2 Drift muss Probleme unterscheiden, gewichten, erklären und in eine Handlung überführen.

17.3 Drift darf keine Ergebnisse erzeugen, die vorrangig dekorativ sind.

17.4 Drift darf keine Produktarbeit fördern, die die Analysequalität verschlechtert.

## 18. Risiko-Audit-Pflicht

18.1 Drift pflegt einen verbindlichen 4-Layer-Risiko-Audit-Stack bestehend aus:
- FMEA-Matrix (`audit_results/fmea_matrix.md`) — Fehlermodi und Priorisierung
- STRIDE Threat Model (`audit_results/stride_threat_model.md`) — Sicherheits-Bedrohungsanalyse
- Fault Tree Analysis (`audit_results/fault_trees.md`) — Kausale Ursachenketten
- Risk Register (`audit_results/risk_register.md`) — Operatives Risikomanagement nach AI-RMF

18.2 **Pflichten bei Signalarbeit:** Bei Hinzufügen, Entfernen oder wesentlicher Änderung eines Signals sind folgende Aktualisierungen vor Merge Pflicht:
- FMEA: mindestens ein FP- und ein FN-Fehlermodus-Eintrag für das betroffene Signal
- FTA: Prüfung ob FT-1 (FP-Kette) oder FT-2 (FN-Kette) um neue Pfade erweitert werden müssen
- Risk Register: betroffene Einträge aktualisieren oder neue anlegen

18.3 **Pflichten bei Architekturänderungen:** Bei Hinzufügen oder Ändern von Input-Pfaden, Output-Kanälen oder Trust Boundaries:
- STRIDE: betroffene Trust Boundary muss S/T/R/I/D/E-Bewertung erhalten
- Risk Register: neue Risiken erfassen

18.4 **Pflichten bei Precision/Recall-Änderungen:** Bei Änderung der Precision oder Recall um mehr als 5 Prozentpunkte:
- FMEA: betroffene RPNs neu berechnen
- Risk Register: Messwerte und Status aktualisieren

18.5 Diese Pflichten gelten gleichermaßen für menschliche Beitragende und KI-Agenten. Ein Agent, der eine signalrelevante Änderung vornimmt ohne die zugehörigen Audit-Artefakte zu aktualisieren, verletzt diese Policy.

18.6 Die Einhaltung wird durch folgende Mechanismen sichergestellt:
- Pre-Push-Hook: Prüft ob geänderte Signale zugehörige Audit-Aktualisierungen haben
- CI-Workflow: `risk-audit-check` Job validiert Vollständigkeit der Audit-Artefakte
- PR-Template: Audit-Checkliste muss vor Merge geprüft werden
- Agent-Instructions: Pflicht-Gate enthält Risk-Audit-Prüfung

18.7 Die vier Audit-Artefakte dürfen nicht gelöscht werden. Inhaltliche Änderungen erfordern Begründung im Commit.

## 19. Telemetrie und Datenschutz

19.1 Drift-Telemetrie ist standardmäßig deaktiviert (Opt-in).

19.2 Telemetrie wird ausschließlich lokal in eine JSONL-Datei geschrieben und nicht an externe Server übertragen.

19.3 Aktivierung und Konfiguration erfolgen über Umgebungsvariablen:
- Aktivieren: `DRIFT_TELEMETRY_ENABLED=1`
- Speicherpfad überschreiben: `DRIFT_TELEMETRY_FILE=/pfad/zur/datei.jsonl`
- Lauf-ID optional setzen: `DRIFT_TELEMETRY_RUN_ID=<wert>`

19.4 Ohne `DRIFT_TELEMETRY_FILE` ist der Standard-Speicherort `.drift/agent_usage.jsonl` im aktuellen Repository-Kontext.

19.5 Erfasste Felder und Zweck:
- `schema_version`: Version des Telemetrieformats für stabile Auswertung.
- `event_type`: Klassifikation des Ereignistyps (`drift_tool_call`).
- `event_id`: Zufällige UUID je Ereignis zur eindeutigen Ereignistrennung.
- `run_id`: Korrelations-ID für zusammenhängende Events eines Prozesses.
- `timestamp`: UTC-Zeitstempel (ISO 8601) für zeitliche Einordnung.
- `tool_name`: Name des aufgerufenen Tools (z. B. `api.scan`, `api.verify`).
- `status`: Ergebnisstatus (`ok` oder `error`).
- `duration_ms`: Laufzeit in Millisekunden für Performance-Analyse.
- `params`: Sanitized Aufrufparameter zur Reproduzierbarkeit; sensible Schlüssel werden maskiert, Zeichenketten gekürzt.
- `input_tokens_est`: Grobe Token-Schätzung der Eingabedaten.
- `output_tokens_est`: Grobe Token-Schätzung der Ausgabedaten.
- `result_summary.keys`: Schlüsselliste der Ergebnisstruktur (ohne vollständigen Inhalt).
- `result_summary.has_error`: Boolescher Marker, ob das Ergebnis als Fehler klassifiziert wurde.
- `error`: Fehlermeldung (`str(exc)`) bei Exceptions.

19.6 Zugriffsmodell: Zugriff auf Telemetriedateien haben nur Akteure mit Dateisystemzugriff auf die jeweilige Arbeitsumgebung (typischerweise Nutzer oder Prozess-Owner derselben Umgebung).

19.7 Aufbewahrung: Drift erzwingt keine automatische Löschfrist; Speicherung, Rotation und Löschung liegen in der Verantwortung des Nutzers bzw. der CI-Umgebung.

19.8 Identifikationsgrenze: `run_id` ist standardmäßig pro Prozesslauf eine frische UUID und kein persistenter Maschinen- oder Nutzer-Identifier.

## 20. Schlussbestimmung

20.1 Diese Policy ist verbindlich.

20.2 Abweichungen von dieser Policy sind nur zulässig, wenn die Abweichung dokumentiert, begründet und als Ausnahme gekennzeichnet ist.

20.3 Im Zweifel gilt stets die Regel mit dem geringeren Interpretationsspielraum und dem höheren Erkenntniswert.

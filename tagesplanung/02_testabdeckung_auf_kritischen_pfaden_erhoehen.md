# Testabdeckung auf kritischen Pfaden erhöhen

## Schnellansicht
- Heute wählen, wenn: Du vor Änderungen mehr Sicherheit brauchst oder ein kritischer Flow schwach getestet ist
- Heute zuerst: Die zwei riskantesten Abläufe benennen und die größte Testlücke markieren
- Feierabendziel: Kritische Risiken sind durch belastbare Tests sichtbar besser abgesichert

## Tagesziel
Nicht einfach mehr Tests schreiben, sondern die riskantesten Abläufe gezielt absichern.

## Heute wählen, wenn
- Du willst bald refactoren und brauchst vorher Schutz
- Bekannte Bugs sind nicht sauber als Regressionstest abgedeckt
- Ein kritischer Flow hat viele Sonderfälle, aber nur oberflächliche Tests
- Du vertraust einem Bereich nicht genug für schnelle Agentenarbeit

## Mögliche Aufgaben für den Tag
- Fehlerfälle und Randfälle testen
- Regressionstests für bekannte Bugs ergänzen
- Property-basierte Tests für Parser, Konfiguration oder Normalisierung ergänzen
- Snapshot- oder Golden-Tests für CLI- oder Report-Ausgaben aufbauen

## Heute zuerst
- Die zwei kritischsten Flows bestimmen
- Das gefährlichste nicht abgesicherte Fehlverhalten notieren
- Einen Testblock auswählen, der heute echten Schutz bringt

## Tagesablauf
### 1. Startblock am Morgen
- Die zwei kritischsten Flows bestimmen
- Kurz festhalten, welches Fehlverhalten du verhindern willst
- Vorhandene Lücken und schwache Tests markieren

### 2. Analyseblock
- Agent Schwachstellen in vorhandenen Tests finden lassen
- Prüfen, welche Fehlerfälle aktuell ungeschützt sind
- Priorisieren, welche Fälle heute den größten Sicherheitsgewinn bringen

### 3. Umsetzungsblock
- Fehlende Negativ- und Edge-Case-Tests ergänzen
- Regressionstests für bekannte problematische Stellen hinzufügen
- Auf robuste, verhaltensorientierte Assertions achten

### 4. Absicherungsblock
- Prüfen, ob die Tests bei Refactorings echten Schutz geben
- Testlauf vollständig ausführen
- Flaky oder zu implementationsnahe Tests nachschärfen

### 5. Tagesabschluss
- Kurz notieren, welche Risiken jetzt abgedeckt sind
- Offene Testlücken für spätere Tage sammeln
- Festhalten, welche Bereiche jetzt sicherer refactorbar sind

## Definition von erledigt
- Mindestens ein kritischer Pfad ist deutlich besser abgesichert
- Neue Tests decken echte Risiken statt nur Codezeilen ab
- Die neuen Tests laufen stabil
- Die wichtigsten Failure-Modes des Tages sind explizit geprüft

## Guter Agent-Fokus
- Identifiziere die kritischsten ungetesteten Pfade in diesem Bereich.
- Ergänze zielgerichtete Regressionstests und Edge-Case-Tests.
- Prüfe, ob bestehende Tests Verhalten oder nur Implementierungsdetails absichern.
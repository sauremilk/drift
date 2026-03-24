# Performance oder Laufzeitverhalten verbessern

## Schnellansicht
- Heute wählen, wenn: Ein Ablauf nervig langsam ist oder unnötig viele Ressourcen zieht
- Heute zuerst: Einen messbaren Workflow auswählen und eine Ausgangsmessung festhalten
- Feierabendziel: Ein echter Engpass ist belegt und messbar verbessert

## Tagesziel
Einen echten Engpass finden und messbar verbessern.

## Heute wählen, wenn
- Ein häufiger Workflow fühlt sich spürbar zu langsam an
- Wiederholte Läufe kosten unnötig viel Zeit oder Ressourcen
- Ein Bereich skaliert schlecht mit größeren Eingaben
- Du vermutest Overhead, aber hast ihn noch nicht gemessen

## Mögliche Aufgaben für den Tag
- Langsame Analysepipeline profilieren
- I/O reduzieren
- Caching verbessern
- Unnötige Wiederholungen oder Mehrfachparsing entfernen
- Parallelisierung dort einführen, wo sie sicher ist

## Heute zuerst
- Einen langsamen Workflow auswählen
- Ein realistisches Messszenario festlegen
- Die Ausgangszeit oder Ausgangskosten notieren

## Tagesablauf
### 1. Startblock am Morgen
- Einen langsamen Workflow auswählen
- Ein realistisches Messszenario festlegen
- Vor dem Eingriff eine Ausgangsmessung sichern

### 2. Analyseblock
- Agent einen Profiling-Ansatz vorbereiten lassen
- Bottleneck isolieren
- Prüfen, ob das Problem CPU, I/O, Parsing oder Datenfluss ist

### 3. Umsetzungsblock
- Die wahrscheinlich wirksamste Optimierung auswählen
- Optimierung implementieren
- Darauf achten, dass Verhalten und Verständlichkeit erhalten bleiben

### 4. Absicherungsblock
- Vorher-Nachher-Messung dokumentieren
- Prüfen, ob Tests und Ergebnisse unverändert korrekt bleiben
- Sicherstellen, dass keine versteckten Regressionsrisiken entstanden sind

### 5. Tagesabschluss
- Verbesserung in klaren Zahlen festhalten
- Notieren, ob sich weitere Optimierungsarbeit lohnt
- Offene Performance-Hypothesen für spätere Tage sammeln

## Definition von erledigt
- Es gibt eine reproduzierbare Ausgangsmessung
- Mindestens ein echter Engpass wurde bearbeitet
- Die Verbesserung ist messbar und dokumentiert
- Funktionales Verhalten blieb stabil

## Guter Agent-Fokus
- Analysiere diesen Workflow auf Laufzeitengpässe und nenne die wahrscheinlich größten Kostentreiber.
- Implementiere eine messbare Optimierung mit minimalem Risiko für Verhaltensänderungen.
- Dokumentiere den Vorher-Nachher-Effekt nachvollziehbar.
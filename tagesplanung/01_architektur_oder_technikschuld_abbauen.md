# Architektur- oder Technikschuld abbauen

## Schnellansicht
- Heute wählen, wenn: Struktur bremst, Änderungen zu lange dauern oder ein Modul zu viele Aufgaben hat
- Heute zuerst: Problemzone wählen und in einem Satz notieren, was daran aktuell weh tut
- Feierabendziel: Ein Bereich ist klarer strukturiert und sicher abgesichert

## Tagesziel
Einen Bereich identifizieren, der langfristig bremst, und ihn in einem Arbeitstag sauber verbessern.

## Heute wählen, wenn
- Änderungen in einem Modul dauern zu lange
- Zu viele Verantwortlichkeiten liegen an einer Stelle
- Kleine Anpassungen erzeugen unerwartete Nebeneffekte
- Du schiebst Änderungen auf, weil der Bereich unübersichtlich ist

## Mögliche Aufgaben für den Tag
- Ein zu großes Modul in klar getrennte Komponenten aufteilen
- Fehlerbehandlung vereinheitlichen
- Konfigurationslogik, CLI-Logik oder Datenzugriff entkoppeln
- Doppelte Hilfsfunktionen konsolidieren

## Heute zuerst
- Problemzone im Projekt auswählen
- In einem Satz festhalten, was daran bremst
- Einen kleinen, klar begrenzten Umbau für heute auswählen

## Tagesablauf
### 1. Startblock am Morgen
- Problemzone im Projekt auswählen
- Vor dem Umbau kurz notieren, was aktuell bremst
- Festlegen, welche Teile heute bewusst nicht angefasst werden

### 2. Analyseblock
- Agent beauftragen, Strukturprobleme zu analysieren
- Eine kleine, saubere Zerlegung oder Vereinfachung auswählen
- Prüfen, ob die Änderung ohne unnötige API-Brüche möglich ist

### 3. Umsetzungsblock
- Refactoring mit minimaler API-Änderung umsetzen lassen
- Änderungen in kleinen, überprüfbaren Schritten halten
- Bei jeder Teiländerung auf Lesbarkeit und Verantwortlichkeiten achten

### 4. Absicherungsblock
- Tests und Typprüfung danach laufen lassen
- Fehlende Regressionstests ergänzen
- Prüfen, ob das Verhalten unverändert geblieben ist

### 5. Tagesabschluss
- Review: Lesbarkeit, Wartbarkeit, Seiteneffekte prüfen
- Kurz dokumentieren, was strukturell besser ist als vorher
- Offene Restpunkte für einen möglichen Folgetag notieren

## Definition von erledigt
- Der betroffene Bereich ist sichtbar klarer strukturiert
- Öffentliche Schnittstellen wurden nicht unnötig beschädigt
- Tests und Typprüfung laufen sauber
- Es gibt keine offenen Zweifel am Verhalten nach dem Umbau

## Guter Agent-Fokus
- Analysiere dieses Modul auf Architekturprobleme und schlage eine kleine, saubere Zerlegung vor.
- Implementiere das Refactoring ohne Verhaltensänderung.
- Ergänze fehlende Tests für das umgebaute Verhalten.
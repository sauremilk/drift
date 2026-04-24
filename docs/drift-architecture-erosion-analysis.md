# **Deterministische Kohärenz und die Quantifizierung dateiübergreifender architektonischer Erosion in Python-Ökosystemen**

Die moderne Softwareentwicklung steht vor einer paradoxen Herausforderung: Während die Werkzeuge zur Erzeugung von Quellcode, insbesondere durch generative Künstliche Intelligenz, eine beispiellose Geschwindigkeit erreicht haben, erodiert die strukturelle Integrität komplexer Systeme schneller als je zuvor. Das Open-Source-Projekt Drift adressiert dieses Problem direkt, indem es eine Lücke schließt, die klassische statische Analysetools wie Ruff, MyPy oder Pylint konstruktionsbedingt offenlassen. Während Ruff lokale Regelverletzungen auf Dateiebene mit extrem hoher Performanz identifiziert, zielt Drift auf die Erkennung der dateiübergreifenden architektonischen Erosion ab, die sich der Modellierung durch traditionelle Linters entzieht.1 Diese Untersuchung analysiert die theoretischen und empirischen Rahmenbedingungen, in denen architektonische Drift und Erosion quantifiziert werden können, und beleuchtet die systematischen Grenzen bestehender Werkzeugketten.

## **Begriffliche Klärung: Architektonische Erosion und Drift im wissenschaftlichen Diskurs**

Um die Funktionsweise von Werkzeugen wie Drift zu verstehen, ist eine präzise Abgrenzung der Begriffe „architektonische Erosion“ (Architecture Erosion, AEr) und „architektonischer Drift“ (Architecture Drift) unerlässlich. In der Forschung wird architektonische Erosion primär als das Phänomen definiert, bei dem die implementierte Architektur (Descriptive Architecture) von der beabsichtigten Architektur (Prescriptive Architecture) abweicht.3 Diese Divergenz ist kein punktuelles Ereignis, sondern ein schleichender Prozess, der oft während der Softwareevolution auftritt, wenn Änderungen akkumuliert werden, ohne das ursprüngliche Architekturmodell zu berücksichtigen.3

## **Definition und Operationalisierung über Dateigrenzen hinweg**

In Tool-Ökosystemen wie Lattix, SonarQube oder Frameworks für Architecture Fitness Functions wird architektonische Erosion über formale Integritätsregeln operationalisiert. Während ein lokaler Fehler (z. B. eine nicht verwendete Variable) innerhalb einer Datei isoliert werden kann, manifestiert sich Erosion typischerweise durch die Verletzung von Modulgrenzen und Schichtungsprinzipien.3

| Begriff | Definition im Forschungskontext | Operationalisierung in Werkzeugen |
| :---- | :---- | :---- |
| Architektonische Erosion | Divergenz zwischen Soll- und Ist-Architektur, die zu Qualitätsverlust führt.3 | Verletzung von Schichtregeln (Layer Violations), zyklische Abhängigkeiten.8 |
| Architektonischer Drift | Unbeabsichtigte Einführung von Mustern, die nicht explizit verboten, aber auch nicht spezifiziert sind.10 | Inkonsistente Verwendung von Entwurfsmustern oder unklare Verantwortlichkeiten.10 |
| Struktureller Zerfall | Abnahme der Kohäsion und Zunahme der Kopplung über die Zeit.3 | Metrikbasierte Überwachung von Fan-In/Fan-Out und Instabilitätsindizes.12 |

Die Forschung identifiziert vier Hauptkategorien von Symptomen, die auf Erosion hinweisen: strukturelle Symptome (z. B. hohe Kopplung), Verletzungssymptome (z. B. Umgehung von Abstraktionsschichten), Evolutionssymptome (z. B. Widerstand gegen Änderungen) und Qualitätssymptome (z. B. abnehmende Wartbarkeit gemäß ISO/IEC 25010).3 Ein zentrales Problem ist, dass eine Architektur „driften“ kann, ohne sofortige funktionale Fehler zu verursachen. Dies führt dazu, dass Teams den schleichenden Verfall erst bemerken, wenn die Kosten für neue Features exponentiell steigen.4

## **Die Rolle der Intentionalität und formaler Modelle**

Ein wesentliches Element der Operationalisierung ist die Existenz einer „Intended Architecture“. Ohne ein Modell dessen, was das System sein *sollte*, kann kein Werkzeug eine Abweichung feststellen.11 In Ansätzen wie dem Architecture Conformance Checking (ACC) wird die Ist-Architektur aus dem Quellcode extrahiert und gegen ein Modell geprüft, das Modulzugehörigkeiten und erlaubte Kommunikationspfade definiert.11 Werkzeuge wie Lattix nutzen hierfür die Dependency Structure Matrix (DSM), um komplexe Abhängigkeiten kompakt darzustellen und Verstöße gegen Schichtungsregeln visuell und algorithmisch zu identifizieren.8

## **Quantifizierungsansätze: Metriken und Graphentheorie**

Die systematische Messung architektonischer Abweichungen erfordert Methoden, die über die statische Analyse einzelner Anweisungen hinausgehen. Hierbei haben sich insbesondere graphentheoretische Modelle und metrikbasierte Analysen bewährt, um den Grad der Erosion objektiv fassbar zu machen.

## **Graphentheoretische Modellierung von Abhängigkeiten**

Softwarearchitekturen können als gerichtete Graphen modelliert werden, wobei Knoten Module oder Dateien repräsentieren und Kanten die Abhängigkeiten (Imports, Funktionsaufrufe) darstellen. Die Quantifizierung von Erosion erfolgt hier durch die Analyse der Grapheneigenschaften.

1. **Zyklenerkennung:** Zyklen zwischen Modulen (Circular Dependencies) sind ein klassisches Indiz für Erosion.9 In einem gesunden, geschichteten System sollte der Abhängigkeitsgraph ein gerichteter azyklischer Graph (DAG) sein. Ein Zyklus deutet darauf hin, dass die Trennung der Belange (Separation of Concerns) aufgehoben wurde.
2. **Kopplungsdichte:** Die Dichte des Graphen gibt Aufschluss darüber, wie stark Komponenten miteinander verwoben sind. Eine zunehmende Kopplungsdichte über die Zeit signalisiert einen Drift hin zu einer monolithischen Struktur, was die Testbarkeit und Austauschbarkeit untergräbt.8
3. **Transitive Blast Radius:** Durch die Analyse indirekter Abhängigkeiten lässt sich messen, wie weit sich eine Änderung in einem Modul durch das System propagiert. Ein hoher transitiver „Blast Radius“ ist ein Zeichen für mangelnde Kapselung.9

## **Metrikbasierte Ansätze und der Instabilitätsindex**

Robert C. Martin definierte Metriken, die heute in Werkzeugen wie SonarQube oder speziellen Python-Frameworks zur Messung von Schichtverletzungen genutzt werden. Zentral sind hierbei die afferente Kopplung (![][image1]) und die efferente Kopplung (![][image2]).

Der Instabilitätsindex ![][image3] wird berechnet als:

![][image4]
Ein Wert von ![][image5] deutet auf eine maximal stabile Komponente hin (viele hängen von ihr ab, sie hängt von niemandem ab), während ![][image6] eine maximal instabile Komponente beschreibt.12 Architektonische Erosion lässt sich quantifizieren, indem die „Entfernung von der Hauptsequenz“ gemessen wird:

![][image7]
Hierbei repräsentiert ![][image8] die Abstraktion der Komponente. Komponenten, die weder abstrakt noch stabil sind (hohes ![][image9]), gelten als „Zone des Schmerzes“, da sie schwer zu ändern, aber dennoch zentral für das System sind.12

## **Messung von Dependency Drift und Schichtverletzungen**

In Python-Projekten wird Dependency Drift oft durch den Vergleich von Import-Graphen über verschiedene Zeitpunkte hinweg gemessen. Spezielle Frameworks für Architecture Fitness Functions (z. B. PyTestArch) erlauben es, Schichtregeln explizit als Tests zu definieren.7

| Quantifizierungsmethode | Beschreibung | Zielsetzung |
| :---- | :---- | :---- |
| Layer Violation Check | Prüfung, ob z. B. der Presentation Layer direkt auf den Persistence Layer zugreift.7 | Durchsetzung von Schichtgrenzen und Verhinderung von „Layer Skipping“.18 |
| Cross-cutting Concern Entanglement | Analyse, wie stark Infrastruktur-Aspekte (Logging, Security) mit der Geschäftslogik verwoben sind.17 | Aufrechterhaltung der Domain-Isolation gemäß Domain-Driven Design (DDD). |
| Co-change Frequency | Messung, wie oft Dateien gemeinsam committet werden, ohne explizite statische Abhängigkeit.17 | Identifikation versteckter (logischer) Kopplung. |

## **Empirische Strategien zur Erkennung von Erosionsmustern**

Um die Häufigkeit und Art von Erosionsmustern in realen Repositories wie drift zu bestimmen, sind Verfahren erforderlich, die historische Daten und semantische Strukturen miteinander verknüpfen.

## **Mining Software Repositories (MSR)**

MSR nutzt die Versionshistorie (Git-Metadata), um die Evolution der Architektur zu rekonstruieren. Ein vielversprechender Ansatz ist die Erstellung von „Alias-Maps“, um Pfadumbenennungen und Löschungen zu verfolgen.20 Dies ist entscheidend, um zu unterscheiden, ob eine Strukturänderung eine geplante Refaktorierung oder eine unbeabsichtigte Erosion darstellt. Durch die Analyse von Metadaten lässt sich bestimmen, ob bestimmte Module überproportional häufig von „Fix-Commits“ betroffen sind, was auf eine architektonische Fragilität hindeuten kann.13

## **AST-Diffing und semantische Anomalieerkennung**

Klassische Diffs auf Zeilenebene (Line-based Diffing) sind unzureichend, um architektonische Verschiebungen zu erfassen, da sie durch Formatierungsänderungen (Surface Churn) verzerrt werden.20 AST-Diffing hingegen analysiert Änderungen am abstrakten Syntaxbaum. Dies ermöglicht es, rein semantische Verschiebungen zu erkennen, wie etwa die Änderung einer Funktionssignatur in einer zentralen Schnittstelle, die dateiübergreifende Auswirkungen hat.20

Ein innovativer Ansatz ist die intermodulare Anomalieerkennung mittels Machine Learning. Hierbei werden statische Strukturen als graphenbasierte Signale (z. B. Graph Convolutional Networks) dargestellt, um Regionen zu identifizieren, in denen Interaktionsmuster von der Norm abweichen.17 Beispielsweise könnte ein Modul, das plötzlich eine hohe Anzahl an Abhängigkeiten zu einem bisher isolierten Subsystem aufbaut, automatisch als „Drift-Risiko“ markiert werden.17

## **Verfahren zur empirischen Bestimmung in Python-Projekten**

Für ein Projekt wie drift könnten folgende Strategien angewandt werden, um die Wirksamkeit des eigenen Ansatzes zu validieren:

* **Injektion von Architekturfehlern:** Bewusste Einführung von Schichtverletzungen in ein Test-Repository, um die Detektionsrate von Drift im Vergleich zu Ruff oder Pylint zu messen.
* **Historische Replay-Analyse:** Anwendung von Drift auf frühere Versionen bekannter Python-Frameworks (z. B. Django, FastAPI), um rückwirkend architektonische Wendepunkte zu identifizieren, die zu technischer Schuld geführt haben.
* **Context Drift Monitoring:** Speziell für KI-unterstützte Teams kann gemessen werden, wie stark KI-generierte Code-Vorschläge von den in copilot-instructions.md oder ähnlichen Dokumenten definierten Regeln abweichen.22

## **Vergleich mit klassischen Tools: Die Grenzen von Ruff, MyPy und Co.**

Der Vergleich zwischen Drift und klassischen Werkzeugen offenbart eine fundamentale Differenz in der Analyse-Tiefe und dem Analyse-Scope. Klassische Tools sind primär darauf ausgelegt, die Korrektheit und Konsistenz einzelner Code-Einheiten sicherzustellen, während Drift die Kohärenz des Gesamtsystems überwacht.

## **Systematische Grenzen bestehender Werkzeuge**

Ruff hat die Python-Entwicklung durch seine Geschwindigkeit revolutioniert, ist jedoch konzeptionell auf lokale Analysen beschränkt.2 Da Ruff in Rust implementiert ist und keine Erweiterbarkeit durch Python-Plugins bietet, können Teams keine komplexen, projektspezifischen Architekturregeln definieren, die eine globale Sicht auf den Abhängigkeitsgraphen erfordern.24

MyPy und Pyright bieten zwar dateiübergreifende Typ-Prüfungen, sind aber „architektonisch agnostisch“.1 Ein Type-Checker garantiert, dass eine Schnittstelle korrekt bedient wird, hinterfragt aber nicht, ob der Aufrufer aufgrund seiner Schichtzugehörigkeit diese Schnittstelle überhaupt kennen darf.7

| Tool | Analyse-Scope | Erkennungsfähigkeit für Erosion | Systematische Grenze |
| :---- | :---- | :---- | :---- |
| **Ruff** | Lokal (Datei).2 | Sehr gering; erkennt nur isolierte Muster (z. B. unused imports). | Fehlender globaler Kontext; keine Modellierung von Modulgrenzen.24 |
| **Pylint** | Repository-weit (begrenzt).2 | Moderat; erkennt Zyklen und Kopplung durch Plugins. | Hoher Performance-Overhead; komplexe Konfiguration für Architekturregeln.24 |
| **MyPy** | Global (Typ-Graph).27 | Gering; erkennt nur Verhaltensdrift (Signaturänderungen). | Fokus auf Typsicherheit, nicht auf strukturelle Designprinzipien.1 |
| **Sonar** | System-weit (Metriken).26 | Hoch; bietet Visualisierungen und Quality Gates. | Oft reaktiv; benötigt oft externe Definitionen der Soll-Architektur.28 |
| **Drift** | Global (Architektur-Graph). | Hoch; spezialisiert auf dateiübergreifende Kohärenz. | Fokus auf Architektur, nicht auf syntaktische Details. |

## **Das Problem des „Vibe Coding“ und Context Drift**

Ein neues Problemfeld, das Drift adressiert, ist der Einfluss von Generativer KI auf die Architektur. Entwickler neigen zunehmend zum sogenannten „Vibe Coding“ — dem schnellen Generieren von Code durch KI-Agenten, wobei traditionelle Architekturplanung oft umgangen wird.28 KI-Modelle generieren oft lokal korrekte Logik, die jedoch redundante Datentypen einführt oder Abstraktionsschichten durchbricht, da sie den globalen Architektur-Kontext nur begrenzt erfassen können.22 Dieser „Context Drift“ führt zu einer stillen Akkumulation von Architekturverletzungen, die von klassischen Lintern nicht bemerkt werden, da jede einzelne Datei für sich genommen „sauber“ aussieht.22

## **Relevante Publikationen und Frameworks**

Die Erforschung von „Cross-Module Architecture Decay Detection“ hat in den letzten Jahren an Bedeutung gewonnen, insbesondere durch die Integration von Architekturregeln in den CI/CD-Prozess.

## **Wissenschaftliche Meilensteine**

Die systematische Mapping-Studie von Liang et al. (2022) bietet eine umfassende Übersicht über 30 Jahre Forschung zur architektonischen Erosion und identifiziert Conformance Checking als effektivste Gegenmaßnahme.3 Ein weiterer wichtiger Rahmen ist das MAPE-K Modell für selbst-adaptive Systeme, das zeigt, wie architektonischer Drift durch kontinuierliche Überwachungs- und Anpassungsschleifen minimiert werden kann.11

Neuere Arbeiten wie SORT-CX führen mathematische Konzepte wie den „Resonanzraum“ ein, um strukturelle Veränderungen unabhängig von der zeitlichen Dynamik zu quantifizieren.30 Hierbei wird Drift als Metrik definiert, die die Stabilität struktureller Fixpunkte unter verschiedenen Transformationen misst.30

## **Werkzeuge und Frameworks im Python-Umfeld**

Neben Drift existieren weitere Ansätze, um architektonische Fitness Functions in Python zu implementieren:

* **PyTestArch:** Erlaubt die Definition von Schichtarchitekturen (z. B. FastAPI-Strukturen) direkt in Pytest-Fixtures. Es ermöglicht explizite Regeln wie should\_not().access\_layers\_that().are\_named("persistence").7
* **ArchUnit-Klone:** Während ArchUnit der Goldstandard in der Java-Welt ist, übertragen Projekte wie PyTestArch dessen Philosophie (Architecture as Code) auf Python.7
* **Multiplayer:** Ein kommerzieller Ansatz, der Dashboards zur Echtzeit-Visualisierung von architektonischem Drift zwischen Diagrammen und Live-Systemen bietet.10
* **Lattix:** Ein spezialisiertes Tool für DSM-Analysen, das auch Python unterstützt und komplexe Abhängigkeitsstrukturen formalisiert.8

## **Fazit: Drift als Enabler für nachhaltige KI-gestützte Entwicklung**

Die Analyse zeigt, dass architektonische Erosion ein multidimensionales Problem ist, das systematische, dateiübergreifende Lösungen erfordert. Klassische statische Analysewerkzeuge wie Ruff erfüllen eine kritische Funktion bei der Aufrechterhaltung der lokalen Code-Qualität, sind jedoch blind für emergente strukturelle Anomalien. Drift positioniert sich hier als notwendige Erweiterung der Tool-Chain, indem es deterministische Prüfverfahren einführt, die die Kohärenz des Gesamtsystems sicherstellen.

Durch die Kombination von graphentheoretischen Quantifizierungsansätzen (wie DSM und Kopplungsmetriken) mit modernen Fitness Functions können Teams architektonische Drift nicht nur empirisch erkennen, sondern proaktiv steuern. In einer Ära, in der Code zunehmend durch KI-Agenten produziert wird, wird die Fähigkeit, architektonische Integrität automatisiert und dateiübergreifend einzufordern, zum entscheidenden Faktor für die langfristige Wartbarkeit und Evolutionsfähigkeit von Software. Drift schließt somit die methodische Lücke zwischen der Geschwindigkeit der KI-unterstützten Codegenerierung und der notwendigen Disziplin einer stabilen Systemarchitektur.

#### **Referenzen**

1. 5 Python Code Quality Tools Built for 100+ Developer Teams \- Qodo, Zugriff am März 24, 2026, [https://www.qodo.ai/blog/python-code-quality-tools/](https://www.qodo.ai/blog/python-code-quality-tools/)
2. FAQ | Ruff \- Astral Docs, Zugriff am März 24, 2026, [https://docs.astral.sh/ruff/faq/](https://docs.astral.sh/ruff/faq/)
3. (PDF) Understanding software architecture erosion: A systematic ..., Zugriff am März 24, 2026, [https://www.researchgate.net/publication/357200965\_Understanding\_software\_architecture\_erosion\_A\_systematic\_mapping\_study](https://www.researchgate.net/publication/357200965_Understanding_software_architecture_erosion_A_systematic_mapping_study)
4. Drift and Erosion in Software Architecture: Summary and Prevention Strategies, Zugriff am März 24, 2026, [https://www.researchgate.net/publication/339385701\_Drift\_and\_Erosion\_in\_Software\_Architecture\_Summary\_and\_Prevention\_Strategies](https://www.researchgate.net/publication/339385701_Drift_and_Erosion_in_Software_Architecture_Summary_and_Prevention_Strategies)
5. Software Architecture, Configuration Management, and Configurable Distributed Systems: A Menage a Trois \- DTIC, Zugriff am März 24, 2026, [https://apps.dtic.mil/sti/tr/pdf/ADA452470.pdf](https://apps.dtic.mil/sti/tr/pdf/ADA452470.pdf)
6. Architecture consistency: State of the practice, challenges and requirements \- Diva-portal.org, Zugriff am März 24, 2026, [http://www.diva-portal.org/smash/get/diva2:1157550/FULLTEXT01.pdf](http://www.diva-portal.org/smash/get/diva2:1157550/FULLTEXT01.pdf)
7. Protecting Architecture with Automated Tests in Python | Tech notes of hands-on software architects, Zugriff am März 24, 2026, [https://handsonarchitects.com/blog/2026/protecting-architecture-with-automated-tests-in-python/?utm\_source=jvm-bloggers.com\&utm\_medium=link\&utm\_campaign=jvm-bloggers](https://handsonarchitects.com/blog/2026/protecting-architecture-with-automated-tests-in-python/?utm_source=jvm-bloggers.com&utm_medium=link&utm_campaign=jvm-bloggers)
8. Lattix | MDS Intelligence, Zugriff am März 24, 2026, [https://www.mdsit.co.kr/mdsit/en/solutions/lattix](https://www.mdsit.co.kr/mdsit/en/solutions/lattix)
9. Dependency Structure Matrix \- NDepend, Zugriff am März 24, 2026, [https://www.ndepend.com/docs/dependency-structure-matrix-dsm](https://www.ndepend.com/docs/dependency-structure-matrix-dsm)
10. Technical Debt Examples & Tutorial \- Multiplayer, Zugriff am März 24, 2026, [https://www.multiplayer.app/system-architecture/technical-debt-examples/](https://www.multiplayer.app/system-architecture/technical-debt-examples/)
11. Architectural Conformance Checking for MAPE-K-based Self-Adaptive Systems \- arXiv, Zugriff am März 24, 2026, [https://arxiv.org/html/2401.16382v3](https://arxiv.org/html/2401.16382v3)
12. Building Evolutionary Architectures: Automated Software Governance \[2 ed.\] 1492097543, 9781492097549 \- DOKUMEN.PUB, Zugriff am März 24, 2026, [https://dokumen.pub/building-evolutionary-architectures-automated-software-governance-2nbsped-1492097543-9781492097549-e-4620406.html](https://dokumen.pub/building-evolutionary-architectures-automated-software-governance-2nbsped-1492097543-9781492097549-e-4620406.html)
13. Software Metrics You Need to Track \- IN-COM DATA SYSTEMS, Zugriff am März 24, 2026, [https://www.in-com.com/blog/software-performance-metrics-you-need-to-track/](https://www.in-com.com/blog/software-performance-metrics-you-need-to-track/)
14. Artifacts in Complex Development Projects \- SE@RWTH, Zugriff am März 24, 2026, [https://www.se-rwth.de/research/Artifacts/](https://www.se-rwth.de/research/Artifacts/)
15. Working with the Dependency Structure Matrix (DSM) \- Lattix documentation, Zugriff am März 24, 2026, [https://docs.lattix.com/lattix/userGuide/Working\_with\_the\_Dependency\_Structure\_Matrix\_DSM.html](https://docs.lattix.com/lattix/userGuide/Working_with_the_Dependency_Structure_Matrix_DSM.html)
16. Dependency Structure Matrix | IntelliJ IDEA Documentation \- JetBrains, Zugriff am März 24, 2026, [https://www.jetbrains.com/help/idea/dsm-analysis.html](https://www.jetbrains.com/help/idea/dsm-analysis.html)
17. Leveraging Machine Learning to Detect Architectural Violations Before Refactoring, Zugriff am März 24, 2026, [https://www.in-com.com/blog/leveraging-machine-learning-to-detect-architectural-violations-before-refactoring/](https://www.in-com.com/blog/leveraging-machine-learning-to-detect-architectural-violations-before-refactoring/)
18. Protecting Architecture with Automated Tests in Python | Tech notes ..., Zugriff am März 24, 2026, [https://handsonarchitects.com/blog/2026/protecting-architecture-with-automated-tests-in-python/](https://handsonarchitects.com/blog/2026/protecting-architecture-with-automated-tests-in-python/)
19. How to Write Clean Code, Zugriff am März 24, 2026, [https://www.augmentcode.com/learn/how-to-write-clean-code](https://www.augmentcode.com/learn/how-to-write-clean-code)
20. Keeping Code-Aware LLMs Fresh: Full Refresh, In-Context Deltas, and Incremental Fine-Tuning \- arXiv, Zugriff am März 24, 2026, [https://arxiv.org/pdf/2511.14022](https://arxiv.org/pdf/2511.14022)
21. Concept drift \- Wikipedia, Zugriff am März 24, 2026, [https://en.wikipedia.org/wiki/Concept\_drift](https://en.wikipedia.org/wiki/Concept_drift)
22. ContextCov: Deriving and Enforcing Executable Constraints from Agent Instruction Files, Zugriff am März 24, 2026, [https://arxiv.org/html/2603.00822v1](https://arxiv.org/html/2603.00822v1)
23. Been using Cursor for months and just realised how much architectural drift it was quietly introducing so made a scaffold of .md files (markdownmaxxing) : r/ClaudeCode \- Reddit, Zugriff am März 24, 2026, [https://www.reddit.com/r/ClaudeCode/comments/1rmlsow/been\_using\_cursor\_for\_months\_and\_just\_realised/](https://www.reddit.com/r/ClaudeCode/comments/1rmlsow/been_using_cursor_for_months_and_just_realised/)
24. Even the Pylint codebase uses Ruff \- Hacker News, Zugriff am März 24, 2026, [https://news.ycombinator.com/item?id=35035618](https://news.ycombinator.com/item?id=35035618)
25. How do Ruff and Pylint compare? \- Python Developer Tooling Handbook, Zugriff am März 24, 2026, [https://pydevtools.com/handbook/explanation/how-do-ruff-and-pylint-compare/](https://pydevtools.com/handbook/explanation/how-do-ruff-and-pylint-compare/)
26. 20 Powerful Static Analysis Tools Every TypeScript Team Needs \- IN-COM DATA SYSTEMS, Zugriff am März 24, 2026, [https://www.in-com.com/blog/20-powerful-static-analysis-tools-every-typescript-team-needs/](https://www.in-com.com/blog/20-powerful-static-analysis-tools-every-typescript-team-needs/)
27. Modern Python Code Quality Setup: uv, ruff, and mypy | by Simone Carolini \- Medium, Zugriff am März 24, 2026, [https://simone-carolini.medium.com/modern-python-code-quality-setup-uv-ruff-and-mypy-8038c6549dcc](https://simone-carolini.medium.com/modern-python-code-quality-setup-uv-ruff-and-mypy-8038c6549dcc)
28. Architecture in SonarQube Cloud | Sonar, Zugriff am März 24, 2026, [https://www.sonarsource.com/solutions/architecture/](https://www.sonarsource.com/solutions/architecture/)
29. Leveraging Large Language Models for Automated Reproduction of Networking Research Results \- arXiv, Zugriff am März 24, 2026, [https://arxiv.org/html/2509.21074v2](https://arxiv.org/html/2509.21074v2)
30. SORT-CX: A Projection-Based Structural Framework for Complex Systems Operator Geometry, Non-Local Kernels, Drift Diagnostics, and Emergent Stability \- Preprints.org, Zugriff am März 24, 2026, [https://www.preprints.org/manuscript/202512.1431](https://www.preprints.org/manuscript/202512.1431)
31. GitHub \- LukasNiessen/ArchUnitTS: ArchUnitTS is an architecture testing library. Specify and ensure architecture rules in your TypeScript app. Easy setup and pipeline integration., Zugriff am März 24, 2026, [https://github.com/LukasNiessen/ArchUnitTS](https://github.com/LukasNiessen/ArchUnitTS)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABYAAAAYCAYAAAD+vg1LAAAAYElEQVR4Xu2QQQoAIAgE+/+niw5FWtYEhpcGvOTuCKX0iSQb03bXjIIVp/0SUiKZCVIiGQEtkEynSa9KhCfSSriYZAShYmt/7O4C5H3X70s9Flrsgj76XOxyQH+Zi/TDKEroQb8LqA96AAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABYAAAAYCAYAAAD+vg1LAAAAY0lEQVR4Xu2QMQ7AIAzE+P+nqTqASCCpg4qyYIkB7s4DpVwyqcZpWZhRsOIrX0JGpDNBRqQjoAPS6TRpaEQ4In1JF5OOIFXs5e7eC733MbN6vaiPBe2F+FWm0WJ93+bIV1wYDyD2P8GteG5GAAAAAElFTkSuQmCC>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAXCAYAAAAyet74AAAAK0lEQVR4XmNgGJrgPw6MFeCVRAa0UUgQkGQa9RQSpQgEqKMQJokNjwLiAAAPNR/hNiJxvwAAAABJRU5ErkJggg==>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAAtCAYAAAATDjfFAAABOklEQVR4Xu3bQQqDMBBAUe9/6ZaCAQkzJi1pTep74MJJiC4/xW4bAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALFHcF/PAAC4SBRmgg0AYBJZmEUzAAAuIMwAACYn2AAAJifYAAAml33DVrTWAQD+UomgFUJohXcEABhulVh7WeU9AQCGWinYAABuSawBAEzuLNiO37dFFwAAC6qjbsYLAGAZ4gUAYHKCDQAAAABmFv2CF81GiM6NZgAA7LJYyuaZnv3ZnwmiGQAAu1Gx1HNOzx4AAA5GBlTrrNY6AACBkRHVOqu1DgBAIIuo4zzbU2vty9breX0PAHB7Z4FU1s72FJ/sie7rGQDA7ZVIimLpG8HWehYAAG/I4irSs6el91kAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/AEsMiBf8Mm6psAAAAASUVORK5CYII=>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAC0AAAAYCAYAAABurXSEAAAAgklEQVR4Xu3OMQrAQAhE0b3/pRMQLNb4TSxWIfjAZlR0rTH+74LqkLqdGj7A3v/0i12qRLe9bEOLFei2l21eBw6KnvZyETYL0H3KRdh06HymIjRDuQibBeg+5QIbReg5yrkR0J1MRWiGcm4Uoh+8TNBCNfvD4y8NvOpi/+j8ZYwxOt0k8GiYakinBwAAAABJRU5ErkJggg==>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAC0AAAAYCAYAAABurXSEAAAAbElEQVR4Xu3RQQqAMAxE0d7/0rqpIIHCn0UmIvMguw8Odq2I/7sONwV/+wtD5R8mxY2kHVLcSNqBw2Z4NA4N8BYcbk+vHIV7HBrgLSgyQaNRVNSnJ0ehHkVGaA+KjI576tO9b0rdMb0nImLKDTZLWafwc5ZbAAAAAElFTkSuQmCC>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAAvCAYAAABexpbOAAABoklEQVR4Xu3c0WkCQRCA4SvFUizlOrGUlJJSLCXxSBaHYU6irndm+T5YcOdhHnz6WcFpAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAOD9fOUBAMDoegdQr33LnmpXNQMAGNZaFD2j575qVzUDAOAOPYOq2lXNAACGFMOnVwT1frGrdlUzAIDh9YogwQYA0EmOnnx/VK89TbWvmgEADKUKnmr2iF57mmpfNQMAGEb7ybJFT7w/E0K99kRrO3vtBwD4kxwjbcY63w8AsCnBdj/fDwCwqSo+qhlXvh8AYFNVfFSzRXuNWzsAALxAFVrV7FE56kY6AAAvtxYdt+a3DgAAneXIGiW8DpdzWjkAAP9Gfh0bIdSaj8uZVw4AADtbYu2YhwAAvI9jHkxjvR4CAAwjRppgAwB4E+fwOUdavgMA8GJzun+meyTWAAA2dJh+4iy+pi3mdI8EGwDADmKEzeFzFP+uRLQBAGzsMF1/Bj2FedSCTawBAOxkCbFjHv6KsSbYAAB2srywiTEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABgQN8pkrRL56JOJQAAAABJRU5ErkJggg==>

[image8]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAYCAYAAADKx8xXAAAARklEQVR4XmNgGJbgP7oAMQCkiX4aYZrooxFZMdEa0RWi83ECdIVEORebAqI14sI4AS5JvBpxSjBQWyM+f6DLYVMzCgYWAACKvS7S96EXvwAAAABJRU5ErkJggg==>

[image9]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABEAAAAXCAYAAADtNKTnAAAARklEQVR4Xu3MMQoAIBADwfz/0wpBC5tsem/hqgwnTU2ruKqE0/ZEkHZHiHZHAJ8gUGEQqDAIBCaOJzQEaHcJpc1dkG76tw063TjI7nwdSAAAAABJRU5ErkJggg==>

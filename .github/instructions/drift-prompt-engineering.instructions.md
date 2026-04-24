---
description: "Nutze diese Instruction, wenn Prompts, Instructions, Skills, Agents oder Copilot-Customization in Drift erstellt, geschärft oder reviewt werden. Fokus: discovery-taugliches Frontmatter, enge applyTo-Scopes, Shared-Partials-Wiederverwendung, Artefaktvertraege und Anti-Halluzinationsregeln fuer Prompt-Engineering."
applyTo:
  - ".github/prompts/**"
  - ".github/instructions/**"
  - ".github/skills/**"
  - ".github/agents/**"
---

# Drift Prompt Engineering

Diese Instruction gilt fuer Prompt-Arbeit im Drift-Workspace. Sie **ergänzt** den
Prompt-Engineering-Modus aus `.github/copilot-instructions.md` und ist **nicht** die
Single Source of Truth fuer Primitive-Wahl, Policy-Gate oder Grundregeln.

Wenn eine Regel bereits in `.github/copilot-instructions.md`,
`.github/instructions/drift-policy.instructions.md`,
`.github/prompts/_partials/*.md` oder im Skill
`.github/skills/drift-agent-prompt-authoring/SKILL.md` steht, wird sie referenziert
und nicht erneut ausformuliert.

Wenn die Aufgabe primär einen neuen oder geänderten Workflow-Prompt unter `.github/prompts/`
betrifft, ist der Skill `.github/skills/drift-agent-prompt-authoring/SKILL.md` die erste
operative Referenz. Diese Instruction liefert nur die zusaetzlichen Dateiregeln.

Diese Instruction **ergänzt** das PFLICHT-GATE aus `.github/instructions/drift-policy.instructions.md`.
Prompt-Arbeit ist nur zulaessig, wenn sie Erkenntnis, Vergleichbarkeit, Einfuehrbarkeit
oder Signalqualitaet verbessert — nicht wenn sie nur mehr Text produziert.

## Zusaetzliche Dateiregeln

- `description` muss den Task-Typ, den Trigger und den Scope benennen. Beispiele:
  "Prompt schaerfen", "Instruction erstellen", "Skill reviewen", "Agent konfigurieren".
- `applyTo` wird nur gesetzt, wenn Dateimatching wirklich gewuenscht ist; on-demand-only
  Regeln bleiben ohne `applyTo`.
- Mehrere `applyTo`-Patterns werden als Array gepflegt, nicht als unleserliche Sammelzeile.
- Datei- oder Ordnerregeln gehoeren in `*.instructions.md`, nicht in `copilot-instructions.md`.
- Prompt-spezifische Arbeitsablaeufe gehoeren in `*.prompt.md`, nicht in Instructions.
- Wiederverwendbare Operator-Abläufe mit Ein-/Ausstiegslogik gehoeren in `SKILL.md`.
- `*.agent.md` ist nur zulaessig, wenn Kontext-Isolation oder andere Tool-Grenzen gebraucht werden.

## Zusatzregeln fuer Prompt-Artefakte

- Prompts unter `.github/prompts/` benennen Ziel, Inputs, Phasen, Artefakte und
  Bewertungslogik explizit und verweisen fuer Standards auf Shared Partials.
- Instructions unter `.github/instructions/` bleiben kurz, datei- oder task-spezifisch
  und enthalten keine zweite Policy-Ebene.
- Skills unter `.github/skills/` benennen in der `description` klar, wann sie genutzt
  werden und wann **nicht**.
- Field-Test-Prompts benennen immer `mick-gsk/drift` als Ziel fuer Findings und Issues.
- Neue Regeln werden erst geschrieben, nachdem geprueft wurde, dass sie nicht schon in
  einer Single Source of Truth existieren.

## Quellen mit Vorrang vor Neuschreibungen

- `.github/prompts/_partials/konventionen.md`
- `.github/prompts/_partials/bewertungs-taxonomie.md`
- `.github/prompts/_partials/issue-filing.md`
- `.github/prompts/_partials/issue-filing-external.md`
- `.github/prompts/_partials/review-checkliste.md`
- `.github/prompts/README.md`
- `.github/skills/drift-agent-prompt-authoring/SKILL.md`
- `.github/copilot-instructions.md`
- `.github/instructions/drift-policy.instructions.md`

## Review-Checkliste

Fuer strukturierte Review-Arbeit an Prompt-Artefakten siehe auch `.github/prompts/_partials/review-checkliste.md`.

- Ist das `description`-Feld discovery-tauglich?
- Ist `applyTo` eng genug?
- Liegt die Regel im richtigen Primitive statt im falschen Dateityp?
- Referenziert die Datei vorhandene Single Sources of Truth statt sie zu kopieren?
- Erzwingt der Text beobachtbares Verhalten statt Stilprosa?
- Wurden Shared Partials referenziert statt kopiert?
- Sind alle repo-spezifischen Aussagen verifiziert?

## Wann nicht verwenden

- Fuer allgemeine Produkt- oder Priorisierungsregeln: `POLICY.md`
- Fuer das operative Pflicht-Gate: `.github/instructions/drift-policy.instructions.md`
- Fuer konkrete Prompt-Ausarbeitung: `.github/skills/drift-agent-prompt-authoring/SKILL.md`

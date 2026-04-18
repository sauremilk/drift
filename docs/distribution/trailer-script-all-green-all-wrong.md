# TRAILER SCRIPT — drift-analyzer

## Meta
- Titel: **All Green. All Wrong.**
- Dauer: ~90 Sekunden
- Emotional Hook: Die schleichende Erkenntnis, dass deine Codebase gerade still zerfällt — und der süchtig machende Moment, in dem du es zum ersten Mal sehen kannst.

---

## Scene-by-Scene Breakdown

### Scene 1 — The Green Lie | Act 1 | 0–5 s
**Visual Direction:** Schwarzer Terminal-Hintergrund. `pytest` läuft durch — grüne Dots, dann `all passed`. Cursor blinkt. Ruhig, clean, vertraut.
**Text Overlay:** —
**Narration (V/O):** "Your tests pass."
**Emotional Target:** FALSE SECURITY

---

### Scene 2 — The Silent Chorus | Act 1 | 5–12 s
**Visual Direction:** Schnelle Schnitte, je 1.5 s: ruff-Output → `0 warnings`. mypy → `Success: no issues found`. GitHub Actions → grüner Haken. PR-Merge-Animation. Alles clean. Alles schnell.
**Text Overlay:** "All green."
**Narration (V/O):** "Your linter finds nothing. Your types check out. CI is green. The pull request ships."
**Emotional Target:** COMPLACENCY

---

### Scene 3 — The Crack | Act 1 | 12–18 s
**Visual Direction:** Langsamer Gegenschnitt. Kamera-Pan über einen langen Diff — normaler Code, aber die Scroll-Geschwindigkeit verlangsamt sich. Leichte Farbentsättigung. Etwas stimmt nicht. Keine visuelle Erklärung — nur das Gefühl.
**Text Overlay:** —
**Narration (V/O):** "And somewhere across three thousand files, something just broke. No error. No warning. No trace."
**Emotional Target:** UNEASE

---

### Scene 4 — The Statement | Act 1 | 18–22 s
**Visual Direction:** Harter Cut auf Schwarz. 1.5 s Stille. Dann faded weißer Text ein, Wort für Wort, mittig. Bleibt stehen.
**Text Overlay:** "Your architecture is drifting."
**Narration (V/O):** —
**Emotional Target:** PARANOIA

---

### Scene 5 — The Lens | Act 2 | 22–28 s
**Visual Direction:** Neuer Terminal. Tippen: `uvx drift-analyzer analyze --repo .` — Enter. Rich-Output beginnt zu erscheinen. Farbige Findings scrollen hoch. Struktur. Farbe. Gewicht. Das ist kein Linter-Output — das sieht aus wie ein Röntgenbild.
**Text Overlay:** —
**Narration (V/O):** "Drift sees what everything else misses. Cross-file erosion — the kind that builds up silently, over weeks, across modules."
**Emotional Target:** CURIOSITY

---

### Scene 6 — The Phantom | Act 2 | 28–38 s
**Visual Direction:** Zoom auf ein einzelnes Finding: PHR-Signal. Farbiger Rich-Output zeigt eine Phantom-Referenz — eine Funktion wird aufgerufen, die nicht existiert. Die Referenz-Zeile ist highlighted, das Ziel ist rot markiert: *not found*. Langsamer Zoom. Die Szene darf atmen.
**Text Overlay:** "This function doesn't exist."
**Narration (V/O):** "A function your agent called — confidently, cleanly — doesn't exist. No test caught it. No linter flagged it. Drift found it in thirty seconds."
**Emotional Target:** SHOCK

---

### Scene 7 — The Clone Drift | Act 2 | 38–47 s
**Visual Direction:** Split-Screen oder schneller Dreier-Cut: drei Code-Module nebeneinander, gleiche Struktur, unterschiedliche Implementierung. PFS-Finding erscheint als Overlay. Die Ähnlichkeit ist sofort sichtbar — die Unterschiede auch.
**Text Overlay:** "Reinvented. Three times."
**Narration (V/O):** "The same pattern. Reimplemented three different ways across three modules. Your agent reinvented it each time — because it couldn't see the whole picture."
**Emotional Target:** RECOGNITION

---

### Scene 8 — The Broken Boundary | Act 2 | 47–55 s
**Visual Direction:** Minimal-Dependency-Graph oder Import-Zeile: `from db.models import ...` in einer Datei unter `api/`. AVS-Finding erscheint — die Grenze zwischen Layern wird als rote Linie visualisiert, die durchbrochen ist.
**Text Overlay:** "The boundary is gone."
**Narration (V/O):** "Your API layer imports directly from your database layer. The architecture boundary was crossed weeks ago. Nobody noticed — until drift."
**Emotional Target:** REVELATION

---

### Scene 9 — Before the First Line | Act 3 | 55–65 s
**Visual Direction:** Neuer Schnitt: Terminal zeigt `drift brief`-Output — strukturierte Guardrails, klar formatiert. Dann: Cut auf IDE. Der drift-brief-Output wird in einen Agenten-System-Prompt eingefügt. Der Agent startet — aber diesmal mit Kontext. Kontrolle, nicht Chaos.
**Text Overlay:** "Before the first line."
**Narration (V/O):** "drift brief injects structural guardrails before your agent writes a single line of code. Not after the damage. Before."
**Emotional Target:** CONTROL

---

### Scene 10 — Safe to Commit | Act 3 | 65–74 s
**Visual Direction:** Terminal: `drift nudge` läuft. Output erscheint: `safe_to_commit: true`. Grüne Farbe. Der Entwickler committed. Kein Zweifel. Kein Nachprüfen. Sicherheit, die aus Wissen kommt — nicht aus Hoffen.
**Text Overlay:** "safe_to_commit: true"
**Narration (V/O):** "drift nudge — real-time feedback, mid-session. Safe to commit, or not. You don't react to erosion anymore. You see it coming."
**Emotional Target:** POWER

---

### Scene 11 — The Facts | Act 4 | 74–80 s
**Visual Direction:** Harter Cut auf Schwarz. Weiße Schrift, zentriert. Drei Zeilen, nacheinander eingeblendet — je 2 Sekunden:
`Deterministic. No LLM.`
`19 signals. ~30 seconds.`
`Zero install: uvx drift-analyzer analyze --repo .`
**Text Overlay:** *(ist das Visual)*
**Narration (V/O):** —
**Emotional Target:** TRUST

---

### Scene 12 — The Tagline | Act 4 | 80–86 s
**Visual Direction:** Schwarz. Weiße Schrift. Tagline erscheint in drei Schlägen — Zeile für Zeile, mit Pause dazwischen:
`Your architecture is drifting.`
`Your linter won't tell you.`
`Drift will.`
**Text Overlay:** *(ist das Visual)*
**Narration (V/O):** "Your architecture is drifting. Your linter won't tell you. Drift will."
**Emotional Target:** CONVICTION

---

### Scene 13 — The Door | Act 4 | 86–90 s
**Visual Direction:** Schwarz. Nur URL, weiß, zentriert. Cursor blinkt daneben. 3 Sekunden. Fertig.
**Text Overlay:** github.com/mick-gsk/drift
**Narration (V/O):** —
**Emotional Target:** ACTION

---

## Call to Action
**Visual:** Schwarzer Hintergrund, weiße URL, blinkender Cursor. Clean. Kein Logo, kein Badge, kein Clutter.
**Tagline:** "Your architecture is drifting. Your linter won't tell you. Drift will."
**URL:** https://github.com/mick-gsk/drift

---

## Director's Notes

1. **Scene 4 ist der Trailer-Moment.** Die 1.5 Sekunden Stille vor "Your architecture is drifting" sind der emotionale Hebel — hier entscheidet sich, ob der Zuschauer bleibt. Nicht kürzen.

2. **Scene 6 (PHR / Phantom) ist die stärkste Demo-Szene.** Die Idee, dass eine Funktion aufgerufen wird, die nicht existiert, ist sofort verständlich, visuell umsetzbar und emotional vernichtend. Diese Szene darf die längste der drei Findings sein.

3. **Act 2 lebt vom Kontrast: Stille Act-1-Oberfläche → farbiger, strukturierter drift-Output.** Der Wechsel von monochromen CI-Screens zu Rich-Terminal-Farbe ist der visuelle Reveal. Nicht abschwächen.

4. **Scene 10 ("safe_to_commit: true") muss sich anfühlen wie Erleichterung.** Hier wechselt der Trailer vom Problem zur Identität. Der Entwickler, der das sieht, ist nicht ängstlich — er ist überlegen. Ruhiges Tempo, kein schneller Schnitt.

5. **Scene 11 (Fakten-Flash) braucht keine Narration.** Die drei Textzeilen — deterministic, 19 signals, zero install — wirken stärker als Schrift-auf-Schwarz als gesprochenes Feature-Listing. Stille verkauft Vertrauen besser als Erklärung.

6. **Tagline in drei Schlägen (Scene 12) ist rhythmisch entscheidend.** Jede Zeile ist ein eigener Beat mit ~0.5 s Pause dazwischen. Die dritte Zeile ("Drift will.") kommt mit der Voice-Over zusammen — das ist der letzte emotionale Schlag.

7. **Die stärkste visuelle Signalwirkung haben PFS (Split-Screen, drei Module) und AVS (durchbrochene Boundary-Linie).** PHR ist narrativ am stärksten, PFS und AVS sind visuell am stärksten. Alle drei brauchen unterschiedliche Screen-Recording-Setups — nicht dasselbe Terminal dreimal.

---

*Narration gesamt: ~160 Wörter · Geschätzte Sprechzeit inkl. Pausen: ~88 s · Alle Fakten aus bereitgestelltem Kontext verifizierbar.*

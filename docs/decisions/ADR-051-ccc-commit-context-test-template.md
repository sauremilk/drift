---
id: ADR-051
status: proposed
date: 2026-04-11
type: signal-design
signal_id: CCC
supersedes:
---

# ADR-051: CCC Commit-Kontext + Boundary-Test-Template

## Problemklasse

`co_change_coupling` (CCC) speichert gegenwärtig in `commit_samples` nur Commit-Hashes — keine Commit-Messages. Der Maintainer sieht: "Diese 5 Dateien ändern sich immer zusammen" + eine Liste von Hex-Hashes, muss aber selbst `git log` aufrufen um zu verstehen **warum** sie sich ko-ändern (Refactoring? Feature? Bug?). Das reduziert den sofortigen Handlungswert erheblich.

Zusätzlich gibt der Fix-Text "Protect with an integration test" ohne Beispiel-Template an — zu abstrakt um handlungsfähig zu sein.

## Heuristik

**Commit-Message-Sammlung:**
```python
# In analyze() bei pair_commit_hashes-Befüllung:
pair_commit_messages[pair].append(commit.message[:60])  # erste 60 Zeichen

# In metadata-Befüllung:
metadata["commit_messages"] = pair_commit_messages[pair][:3]  # max. 3 Messages
```

**Fix-Text-Template:**
```
Co-change coupling detected. Recent co-change commits:
  - "{message1}"
  - "{message2}"

If coupling is intentional (shared domain boundary):
  → Add an integration test:
    def test_<module_a>_<module_b>_sync():
        # Verify both modules expose consistent contracts
        assert matches_contract(module_a, module_b)

If coupling is accidental (layering issue):
  → Extract shared logic into a new module:
    # src/<domain>/<shared>.py
```

## Scope

`git_dependent` — bestehende Einstufung bleibt. `commit.message` ist bereits als Feld in `CommitInfo` vorhanden und wird für Merge-Detection genutzt (d.h. keine neue Abhängigkeit).

## Erwartete FP-Klassen

- Commit-Messages enthalten sensible Informationen (Ticket-IDs, interne Codewords) → werden in Output aufgenommen. Akzeptabel da Drift ohnehin lokal läuft und keine externen Outputs erzeugt ohne explizite Konfiguration.
- Leere oder nichtssagende Messages ("WIP", "fix") → zeigen wenig Kontext, aber besser als Hashes

## Erwartete FN-Klassen

- Pair hat > 3 signifikante Co-Changes mit verschiedenen Motiven → nur ersten 3 gezeigt, Rest abgeschnitten

## Fixture-Plan

- TP-Fixture: `ccc_with_commit_messages` — Pair mit 5+ Co-Changes, commit_messages in Metadata vorhanden
- Der bestehende CCC-TP-Fixture wird erweitert

## FMEA-Vorab-Eintrag

| Failure Mode | Severity | Occurrence | Detection | RPN |
|---|---|---|---|---|
| FP: Sensible Commit-Messages in Output | 5 | 3 | 5 | 75 |
| FN: Nur 3 Messages zu wenig Kontext bei vielen Co-Changes | 3 | 4 | 7 | 84 |

## Validierungskriterium

1. CCC-Findings enthalten `commit_messages` in Metadata (Liste mit 1–3 Strings).
2. Fix-Text für CCC enthält Boundary-Test-Template.
3. TP-Fixture `ccc_with_commit_messages` → Finding mit non-leerer `commit_messages`-Liste.
4. `pytest tests/test_precision_recall.py` — CCC Recall ≥ 0.80 (Baseline).

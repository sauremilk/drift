# System Misalignment Signal (SMS)

**Signal ID:** `SMS`  
**Full name:** System Misalignment Score  
**Type:** Scoring signal (contributes to drift score)  
**Default weight:** `0.08`  
**Scope:** cross_file

---

## What SMS detects

SMS detects when code introduces **patterns, dependencies, or conventions not established in the target module** — changes that solve a local task correctly but weaken global cohesion. This is the AI "style mismatch" problem: generated code works but doesn't fit the surrounding codebase.

### Before — misaligned logging

```python
# All other modules use structlog:
# services/auth.py, services/billing.py → import structlog

# services/notification.py (AI-generated)
import logging   # ← rest of project uses structlog
logger = logging.getLogger(__name__)

def send_notification(user, message):
    logger.info(f"Sending to {user}")   # ← wrong logger, wrong format
```

The function works, but uses the wrong logging library/convention.

### After — aligned with project conventions

```python
# services/notification.py
import structlog   # ← matches project convention

logger = structlog.get_logger(__name__)

def send_notification(user, message):
    logger.info("sending_notification", user=user)   # ← structured logging
```

---

## Why system misalignment matters

- **Convention erosion** is silent — each misaligned addition works perfectly in isolation.
- **Maintenance fragmentation** — different conventions require different expertise and tooling.
- **AI is convention-unaware** — LLMs default to the most common pattern (e.g., `import logging`), not the project-specific one (e.g., `import structlog`).
- **Compounds over time** — each misalignment makes the "wrong" pattern look more established.

---

## How the score is calculated

SMS compares the conventions in a module against the dominant conventions in its containing package or project:

1. **Extract convention fingerprints** — import patterns, naming styles, error handling approaches.
2. **Build package-level convention baselines** — what patterns are used by the majority of modules.
3. **Score deviation** — modules using conventions not present in the baseline receive higher scores.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix SMS findings

1. **Adopt the dominant pattern** — align with what the rest of the package uses.
2. **If the new pattern is better** — create a migration plan to move the whole package to the new convention, rather than mixing both.
3. **Document project conventions** — make it explicit which libraries, patterns, and styles are preferred.
4. **Configure AI tools** — provide context rules or `.cursorrules` files so AI assistants generate aligned code.

---

## Configuration

```yaml
# drift.yaml
weights:
  system_misalignment: 0.08   # default weight (0.0 to 1.0)
```

---

## Detection details

1. **Parse all imports and patterns** from AST.
2. **Group by containing package** (parent directory).
3. **Establish baselines** — the convention used by ≥ 50% of modules becomes the baseline.
4. **Score deviations** — modules deviating from baseline receive findings proportional to the deviation count.
5. **Cross-file analysis** — compares across all files, not just individual files.

SMS is deterministic and AST-based.

---

## Related signals

- **AVS (Architecture Violation)** — detects import-level boundary violations. SMS detects convention-level deviations.
- **PFS (Pattern Fragmentation)** — detects multiple implementations of the same intent. SMS detects the use of non-established patterns.

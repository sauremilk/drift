# Circular Import Signal (CIR)

**Signal ID:** `CIR`  
**Full name:** Circular Import  
**Type:** Report-only signal (weight 0.0 — does not contribute to drift score)  
**Default weight:** `0.0`  
**Scope:** cross_file

---

## What CIR detects

CIR detects **circular import chains** within Python packages — module A imports B, B imports C, C imports A. These cycles cause `ImportError` at runtime, unexpected `None` values from partially-initialized modules, and make the codebase resistant to refactoring.

### Example finding

```
circular_import: cycle detected
  services/auth.py → services/user.py → services/auth.py
  Cycle length: 2
  → Score: 0.55 (MEDIUM)
```

### Before — circular import

```python
# services/auth.py
from services.user import get_user_by_token

def authenticate(token):
    return get_user_by_token(token)

# services/user.py
from services.auth import verify_token   # ← circular!

def get_user_by_token(token):
    if verify_token(token):
        return User.query.get(token.user_id)
```

### After — broken cycle

```python
# services/auth.py
from services.user import get_user_by_token

def authenticate(token):
    return get_user_by_token(token)

def verify_token(token):
    return token is not None and not token.expired

# services/user.py
from services.auth import verify_token   # ← no longer circular

def get_user_by_token(token):
    if verify_token(token):
        return User.query.get(token.user_id)
```

Or restructure by extracting `verify_token` into a separate `services/token.py`.

---

## Why circular imports matter

- **Runtime import failures** — Python's import system may return partially-initialized modules, causing `AttributeError`.
- **Import order sensitivity** — the application works only if modules are imported in a specific order.
- **AI adds imports freely** — code assistants add the shortest import path without checking for cycles.
- **Refactoring resistance** — every attempt to move code triggers new cycle errors.

---

## How the score is calculated

CIR builds a directed import graph and runs cycle detection:

1. **Build import graph** — edges from each module to its imports.
2. **Run DFS cycle detection** — find all strongly connected components.
3. **Score by cycle length and count** — longer cycles and more involved modules score higher.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## Status

CIR is **report-only** (weight `0.0`) until precision and recall have been validated. Known limitation: conditional imports (`if TYPE_CHECKING:`) may produce false positives.

---

## How to fix CIR findings

1. **Move shared code** to a third module imported by both.
2. **Use dependency inversion** — depend on interfaces, not implementations.
3. **Defer imports** — move imports inside functions (last resort).
4. **Use `TYPE_CHECKING` guards** — for type-annotation-only imports.

---

## Configuration

```yaml
# drift.yaml
weights:
  circular_import: 0.0   # report-only (set > 0.0 to make scoring-active)
```

---

## Detection details

1. **Parse import statements** from all Python files.
2. **Build directed graph** — module → imported module.
3. **Find cycles** using Tarjan's algorithm (strongly connected components).
4. **Report** each cycle with participating modules and import lines.

CIR is deterministic and AST-based.

---

## Related signals

- **AVS (Architecture Violation)** — detects directional import violations. CIR detects circular import violations.
- **TSA (TypeScript Architecture)** — includes cycle detection for TS/JS. CIR is the Python equivalent.

# Example Findings

This page shows the kind of output that makes drift tangible during evaluation.

These examples are adapted from the reproducible ground-truth fixtures used in the test suite, so they are not decorative screenshots. They represent concrete signal shapes drift is designed to surface.

## 1. Pattern Fragmentation

**Short code example**

```python
# services/handler_a.py
def handle_a(data):
    try:
        process(data)
    except ValueError as error:
        raise AppError(str(error)) from error


# services/handler_b.py
def handle_b(data):
    try:
        process(data)
    except Exception as error:
        logger.error("Failed: %s", error)
        return None


# services/handler_c.py
def handle_c(data):
    try:
        process(data)
    except Exception:
        sys.exit(1)
```

**Finding**

- Signal: `PFS` (Pattern Fragmentation)
- Typical result: `3 different error-handling patterns in services/`

**Why it matters**

Three files solve the same failure mode with three incompatible behaviors: raise, log-and-return, and terminate the process. That increases debugging cost, makes retries inconsistent, and teaches the team that the local file matters more than the module contract.

**How to fix it**

Pick one error-handling contract for the module, extract it into a shared helper or base abstraction, and refactor the outliers to match it.

## 2. Mutant Duplicate

**Short code example**

```python
# utils/formatters.py
def format_currency(amount: float, currency: str = "EUR") -> str:
    if amount < 0:
        prefix = "-"
        amount = abs(amount)
    else:
        prefix = ""
    formatted = f"{amount:.2f}"
    integer_part, decimal_part = formatted.split(".")
    return f"{prefix}{integer_part}.{decimal_part} {currency}"


# utils/money.py
def format_money(amount: float, currency: str = "EUR") -> str:
    if amount < 0:
        prefix = "-"
        amount = abs(amount)
    else:
        prefix = ""
    formatted = f"{amount:.2f}"
    integer_part, decimal_part = formatted.split(".")
    return f"{prefix}{integer_part}.{decimal_part} {currency}"
```

**Finding**

- Signal: `MDS` (Mutant Duplicate)
- Typical result: `Exact-duplicate functions across two files`

**Why it matters**

Copied helpers drift apart later. One version gets a bug fix or a locale rule, the other does not. The problem is not just duplication count; it is hidden future divergence in logic that the team already considers shared.

**How to fix it**

Extract the formatter into one shared module, keep one public entry point, and replace local copies with imports.

## 3. Architecture Violation

**Short code example**

```python
# api/routes.py
def get_users():
    return []


# db/models.py
from api.routes import get_users


class User:
    pass
```

**Finding**

- Signal: `AVS` (Architecture Violation)
- Typical result: `DB layer importing from API layer (upward violation)`

**Why it matters**

The database layer now depends on the API layer, which inverts the intended direction of knowledge. That makes refactoring harder, increases cycle risk, and couples storage concerns to transport concerns.

**How to fix it**

Move the shared behavior or type into a neutral module, or invert the dependency through an interface so that `db/` no longer imports `api/`.

## 4. Doc-Implementation Drift

**Short code example**

```markdown
# README.md

- `src/` — main source code
- `plugins/` — extension plugins
- `workers/` — background workers
```

Repository reality:

```text
src/
# plugins/ and workers/ do not exist
```

**Finding**

- Signal: `DIA` (Doc-Implementation Drift, report-only)
- Typical result: `plugins/ and workers/ referenced but missing`

**Why it matters**

Teams use the README as architecture guidance. If the documented structure is stale, onboarding slows down and new code is placed according to fiction rather than reality.

**How to fix it**

Either remove the stale references from the README or create the missing directories if they still represent the intended architecture.

## 5. Temporal Volatility

**Short code example**

```python
# app/volatile.py
def volatile_func(x):
    if x > 0:
        return x * 2
    return -x
```

Repository history context:

```text
app/volatile.py
- 80 total commits
- 8 unique authors
- 25 changes in 30 days

Neighboring files in app/
- mostly single-digit commits and low recent churn
```

**Finding**

- Signal: `TVS` (Temporal Volatility)
- Typical result: `Extreme churn outlier among stable files`

**Why it matters**

The code itself may look small and harmless, but the history says the file is a coordination hotspot. Repeated edits by many authors usually point to unclear ownership, unstable responsibilities, or architecture that forces unrelated changes into the same place.

**How to fix it**

Split responsibilities, assign clear ownership, and reduce the number of reasons this file needs to change. If the churn is intentional, document that explicitly so the hotspot is understood rather than accidental.

## Reproducibility

These examples are based on the ground-truth fixtures in `tests/fixtures/ground_truth.py`:

- `pfs_tp`
- `mds_tp`
- `avs_tp`
- `dia_tp`
- `tvs_tp`

Use them when you want to inspect concrete signal shapes before running drift on your own repository.

# Pattern Fragmentation Signal (PFS)

**Signal ID:** `PFS`
**Full name:** Pattern Fragmentation Score
**Type:** Scoring signal (contributes to drift score)
**Default weight:** `0.16`

---

## What PFS detects

PFS identifies modules where the **same category of code pattern** (e.g. error handling, data validation, logging) is implemented in **multiple incompatible ways**. This fragmentation is a strong indicator of architectural drift — often caused by different AI generation sessions producing slightly different implementations of the same concept.

### Before — fragmented error handling

```python
# services/payment_service.py
def process_payment(amount):
    try:
        validate(amount)
        return {"status": "ok"}
    except ValueError as e:
        raise PaymentError(str(e)) from e

def refund_payment(transaction_id):
    try:
        result = lookup(transaction_id)
        return True
    except Exception as e:        # ← bare except, different style
        print(e)
        return False

def cancel_payment(payment_id):
    result = lookup(payment_id)
    if result is None:             # ← no try/except at all
        logger.warning("Not found")
        return False
    return True
```

Three functions, three different error handling approaches in the same module. PFS flags this as fragmentation.

### After — consolidated pattern

```python
# services/payment_service.py
class PaymentError(Exception):
    pass

def process_payment(amount):
    try:
        validate(amount)
        return {"status": "ok"}
    except ValueError as e:
        raise PaymentError(str(e)) from e

def refund_payment(transaction_id):
    try:
        result = lookup(transaction_id)
        return True
    except LookupError as e:
        raise PaymentError(str(e)) from e

def cancel_payment(payment_id):
    try:
        result = lookup(payment_id)
        return True
    except LookupError as e:
        raise PaymentError(str(e)) from e
```

One consistent error handling pattern across the module.

---

## Why pattern fragmentation matters

- **Maintenance cost multiplies** — each variant requires separate understanding and testing.
- **Bugs hide in deviations** — the `except Exception: print(e)` variant silently swallows errors that the other variants would propagate.
- **Onboarding friction** — new contributors cannot determine which pattern is the intended standard.
- **AI generation amplifies fragmentation** — LLMs generate plausible but subtly different implementations each session, leading to variant accumulation over time.

---

## How the score is calculated

$$
\text{fragmentation\_score} = 1 - \frac{1}{\text{num\_variants}}
$$

| Variants | Score | Severity |
|----------|-------|----------|
| 2        | 0.50  | MEDIUM   |
| 3        | 0.67  | MEDIUM   |
| 4        | 0.75  | HIGH     |
| 5+       | 0.80+ | HIGH     |

**Spread boost:** When non-canonical instances spread across many files (> 2), a spread factor is applied:

$$
\text{spread\_factor} = \min\!\bigl(1.5,\; 1.0 + (\text{non\_canonical\_count} - 2) \times 0.04\bigr)
$$

The score is capped at 1.0.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix PFS findings

1. **Identify the canonical variant** — PFS reports which variant is used most often (the "canonical" pattern). This is your consolidation target.
2. **Migrate deviating instances** — Refactor non-canonical usages to match the dominant pattern. PFS lists affected files and line numbers.
3. **Extract shared abstractions** — If variants serve genuinely different purposes, extract them into clearly named helpers or base classes.
4. **Add linting rules** — Once consolidated, add project-specific lint rules or code review checklists to prevent re-fragmentation.

---

## Configuration

In `drift.yaml` or `pyproject.toml`:

```yaml
# drift.yaml
weights:
  pattern_fragmentation: 0.16   # default weight (0.0 to 1.0)
```

```toml
# pyproject.toml
[tool.drift.weights]
pattern_fragmentation = 0.16
```

Set to `0.0` to disable PFS scoring entirely. Increase the weight to prioritize fragmentation findings.

---

## Example output

```json
{
  "signal_type": "pattern_fragmentation",
  "severity": "high",
  "score": 0.75,
  "title": "error handling: 4 variants in services/",
  "description": "4 error handling variants in services/ (6/10 use canonical pattern).\n  - payment_service.py:14 (refund_payment)\n  - payment_service.py:22 (cancel_payment)\n  - order_service.py:8 (create_order)",
  "fix": "Consolidate to the dominant pattern (6×). 4 deviations in: payment_service.py, order_service.py.",
  "metadata": {
    "category": "error handling",
    "num_variants": 4,
    "canonical_count": 6,
    "total_instances": 10
  }
}
```

---

## Detection details

PFS uses the following algorithm:

1. **Collect patterns** from all parsed files (AST-extracted pattern instances with category and fingerprint).
2. **Group by module** (parent directory) and pattern category.
3. **Normalize fingerprints** — async/sync variants are treated as equivalent to reduce false positives.
4. **Count unique variants** per module using fingerprint hashing.
5. **Identify the canonical variant** (most-used) and report deviations.

PFS is deterministic, AST-only, and does not require git history or LLM calls.

---

## Related signals

- **MDS (Mutant Duplicates)** — detects near-identical functions. MDS finds copy-paste code; PFS finds the same *intent* implemented differently.
- **COD (Code Duplication)** — detects exact or near-exact code blocks. COD finds duplication; PFS finds inconsistency.

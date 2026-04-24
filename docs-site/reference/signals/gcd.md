# Guard Clause Deficit Signal (GCD)

**Signal ID:** `GCD`
**Full name:** Guard Clause Deficit
**Type:** Scoring signal (contributes to drift score)
**Default weight:** `0.03`
**Scope:** file_local

---

## What GCD detects

GCD detects modules where public, non-trivial functions **uniformly lack guard clauses and input validation**. It also flags excessive nesting depth, indicating missing early returns. Functions that accept any input without validation are the top vector for runtime errors.

### Before — no guard clauses

```python
def process_order(order, user, config):
    items = order["items"]
    total = sum(item["price"] * item["qty"] for item in items)
    if config["discount_enabled"]:
        if user["membership"] == "premium":
            total *= 0.9
            if total > config["free_shipping_threshold"]:
                shipping = 0
            else:
                shipping = config["shipping_rate"]
        else:
            shipping = config["shipping_rate"]
    else:
        shipping = config["shipping_rate"]
    return {"total": total, "shipping": shipping}
```

No input validation, deep nesting, and any `None` or missing key causes a crash.

### After — with guard clauses

```python
def process_order(order, user, config):
    if not order or "items" not in order:
        raise ValueError("order must contain 'items'")
    if not user:
        raise ValueError("user is required")

    items = order["items"]
    if not items:
        return {"total": 0, "shipping": 0}

    total = sum(item["price"] * item["qty"] for item in items)

    is_premium = user.get("membership") == "premium"
    if config.get("discount_enabled") and is_premium:
        total *= 0.9

    threshold = config.get("free_shipping_threshold", float("inf"))
    shipping = 0 if total > threshold else config.get("shipping_rate", 0)

    return {"total": total, "shipping": shipping}
```

---

## Why guard clause deficits matter

- **Runtime crashes** — missing validation makes functions fragile to unexpected inputs.
- **Deep nesting reduces readability** — guard clauses + early returns flatten control flow.
- **AI code often lacks validation** — LLMs generate the happy path, assuming correct inputs.
- **Defense in depth** — even if callers validate, functions should be self-protective.

---

## How the score is calculated

GCD evaluates each public function for:

1. **Guard clause presence** — does the function check inputs before processing?
2. **Early return usage** — does the function use early returns to avoid deep nesting?
3. **Nesting depth** — maximum nesting level as a proxy for missing guards.
4. **Module-level uniformity** — if *all* public functions lack guards, the score is higher.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix GCD findings

1. **Add input validation at the top** — check for None, missing keys, invalid types.
2. **Use early returns** — handle edge cases first, then proceed with the main logic.
3. **Flatten nesting** — replace nested if/else chains with guard clauses.
4. **Use assertion helpers** — create project-specific validation utils for common checks.

---

## Configuration

```yaml
# drift.yaml
weights:
  guard_clause_deficit: 0.03   # default weight (0.0 to 1.0)
```

---

## Detection details

1. **Parse all public functions** (no `_` prefix) from AST.
2. **Filter to non-trivial functions** (minimum LOC threshold).
3. **Check for guard patterns** — assertions, raises, early returns in the first few statements.
4. **Measure nesting depth** — maximum logical nesting level.
5. **Score at module level** — higher when all functions lack guards.

GCD is deterministic and AST-only.

---

## Related signals

- **BEM (Broad Exception Monoculture)** — detects poor error handling. GCD detects missing input validation.
- **EDS (Explainability Deficit)** — detects unexplained complex code. GCD detects unprotected complex code.
- **CXS (Cognitive Complexity)** — measures raw complexity. GCD specifically targets missing guard clauses that cause unnecessary complexity.

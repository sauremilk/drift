# Cognitive Complexity Signal (CXS)

**Signal ID:** `CXS`  
**Full name:** Cognitive Complexity  
**Type:** Report-only signal (weight 0.0 — does not contribute to drift score)  
**Default weight:** `0.0`  
**Scope:** file_local

---

## What CXS detects

CXS detects functions exceeding a **cognitive-complexity threshold**. Unlike cyclomatic complexity (which counts decision points), cognitive complexity measures how hard code is to *understand* — penalizing deeply nested structures, breaks in linear flow, and complex boolean expressions.

### Example finding

```
cognitive_complexity in services/order_processor.py::validate_order
  Cognitive complexity: 23 (threshold: 15)
  Contributors: 4 nested if-blocks, 2 loops with break, 1 recursive call
  → Score: 0.65 (MEDIUM)
```

### Before — high cognitive complexity

```python
def validate_order(order, rules):
    for rule in rules:
        if rule.type == "quantity":
            for item in order.items:
                if item.quantity > 0:
                    if item.quantity <= rule.max:
                        if item.product.active:
                            continue
                        else:
                            return False
                    else:
                        return False
                else:
                    return False
    return True
```

### After — reduced complexity

```python
def validate_order(order, rules):
    for rule in rules:
        if rule.type == "quantity" and not _check_quantity_rule(order, rule):
            return False
    return True

def _check_quantity_rule(order, rule):
    return all(
        0 < item.quantity <= rule.max and item.product.active
        for item in order.items
    )
```

---

## Why cognitive complexity matters

- **Understanding cost** — every nesting level multiplies the mental effort needed to trace execution.
- **AI generates complex code** — LLMs tend to produce single-function solutions with deep nesting rather than decomposed logic.
- **Bug density correlates with complexity** — research consistently shows that complex functions contain more defects.
- **Maintenance friction** — complex functions resist modification because changes have unpredictable side effects.

---

## How the score is calculated

CXS follows the **SonarSource cognitive complexity model**:

1. **Increment** for each control-flow break (if, for, while, catch, switch cases, logical operators in conditions).
2. **Nesting bonus** — each control-flow break inside a nested structure adds the current nesting level as a bonus.
3. **No increment** for shorthand structures (ternary operators, null-coalescing).

$$
\text{complexity} = \sum (\text{base\_increment} + \text{nesting\_bonus})
$$

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## Status

CXS is **report-only** (weight `0.0`) until precision and recall have been validated. It appears in reports but does not affect the drift score.

---

## How to fix CXS findings

1. **Extract helper functions** — decompose complex functions into smaller, well-named helpers.
2. **Use early returns** — guard clauses flatten nesting.
3. **Replace nested conditions with boolean logic** — combine conditions at the same level.
4. **Use comprehensions or generators** — replace nested loops with flat expressions.

---

## Configuration

```yaml
# drift.yaml
weights:
  cognitive_complexity: 0.0   # report-only (set > 0.0 to make scoring-active)

thresholds:
  cognitive_complexity_max: 15   # threshold per function
```

---

## Detection details

1. **Parse all functions** from AST.
2. **Walk the AST** counting cognitive-complexity increments.
3. **Apply nesting bonuses** for structures inside other structures.
4. **Report functions** exceeding the threshold.

CXS is deterministic and AST-only.

---

## Related signals

- **EDS (Explainability Deficit)** — detects complex code without documentation. CXS measures complexity directly.
- **GCD (Guard Clause Deficit)** — detects missing early returns. GCD findings often cause high CXS scores.

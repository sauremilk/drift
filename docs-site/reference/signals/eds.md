# Explainability Deficit Signal (EDS)

**Signal ID:** `EDS`
**Full name:** Explainability Deficit Score
**Type:** Scoring signal (contributes to drift score)
**Default weight:** `0.09`
**Scope:** file_local

---

## What EDS detects

EDS flags **complex functions that lack documentation and tests** — code that was accepted into the codebase without being understood. This is especially prevalent with AI-generated code, where developers accept suggestions without verifying they understand the logic.

### Before — unexplained complex function

```python
def process_transaction(data, config, user, mode="standard"):
    result = {}
    if mode == "standard":
        for item in data.get("items", []):
            if item.get("type") == "credit":
                if config.allow_credits:
                    amount = item["amount"] * config.rate
                    if user.balance >= amount:
                        result[item["id"]] = {"status": "approved", "amount": amount}
                    else:
                        result[item["id"]] = {"status": "declined", "reason": "balance"}
                else:
                    result[item["id"]] = {"status": "skipped"}
            elif item.get("type") == "debit":
                # ... more nested logic
                pass
    return result
```

Complex branching logic with no docstring, no comments, no tests.

### After — explained and tested

```python
def process_transaction(data, config, user, mode="standard"):
    """Process a batch of transaction items against user balance.

    Args:
        data: Transaction payload with 'items' list.
        config: Processing rules (allow_credits, rate).
        user: User with current balance.
        mode: Processing mode ('standard' or 'express').

    Returns:
        Dict mapping item IDs to status results.
    """
    # ... implementation with inline comments for non-obvious logic
```

---

## Why explainability deficits matter

- **"Accepted without understanding"** — the core risk. Code that nobody understands cannot be safely maintained.
- **AI-generated code is particularly risky** — it often works but uses non-obvious patterns that the accepting developer may not fully grasp.
- **Bug localization becomes impossible** — when complex logic fails, the absence of documentation makes diagnosis much harder.
- **Knowledge loss is permanent** — the generating context (AI conversation, prompt) is typically lost after the session.

---

## How the score is calculated

EDS combines multiple factors:

1. **Complexity** — cyclomatic complexity or nesting depth of the function.
2. **Documentation absence** — no docstring AND no inline comments.
3. **Test absence** — no corresponding test function found.
4. **AI attribution** (when available) — higher weight if function appears AI-generated.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix EDS findings

1. **Add a docstring** — explain what the function does, its parameters, return value, and any non-obvious behavior.
2. **Add inline comments** for complex branches — explain *why*, not *what*.
3. **Write at least one test** — demonstrates understanding and provides a specification.
4. **Simplify if possible** — if you can't explain it, consider whether the complexity is necessary.

---

## Configuration

```yaml
# drift.yaml
weights:
  explainability_deficit: 0.09   # default weight (0.0 to 1.0)

thresholds:
  high_complexity: 10   # cyclomatic complexity threshold
```

---

## Detection details

1. **Parse all functions** from AST with complexity metrics.
2. **Filter** to functions exceeding the `high_complexity` threshold.
3. **Check** for docstring presence and inline comment density.
4. **Check** for corresponding test functions (name-based matching).
5. **Apply AI attribution boost** if function appears in AI-attributed commits.

EDS is deterministic and AST-only. AI attribution is optional (requires git history).

---

## Related signals

- **CXS (Cognitive Complexity)** — measures raw complexity. EDS combines complexity with documentation absence.
- **TPD (Test Polarity Deficit)** — checks test quality. EDS checks test existence for complex code.
- **DIA (Doc-Implementation Drift)** — checks doc-code consistency. EDS checks for documentation presence.

# Naming Contract Violation Signal (NBV)

**Signal ID:** `NBV`
**Full name:** Naming Contract Violation
**Type:** Scoring signal (contributes to drift score)
**Default weight:** `0.04`
**Scope:** file_local

---

## What NBV detects

NBV detects functions whose **name implies a behavioral contract that the implementation doesn't fulfill**. For example, `validate_email()` that never raises or returns a boolean, or `is_admin()` that modifies state. This is a proxy for "intention drift" — the function's name promises something the code doesn't deliver.

### Before — broken naming contract

```python
def validate_user(user_data):
    # Name says "validate" but never raises or returns False
    user_data["created_at"] = datetime.now()
    user_data["status"] = "active"
    return user_data

def is_authenticated(request):
    # Name says "is_" (predicate) but modifies session state
    request.session["last_check"] = time.time()
    token = request.headers.get("Authorization")
    if token:
        request.session["user"] = decode_token(token)
        return True
    return False
```

### After — name matches behavior

```python
def prepare_user(user_data):
    """Prepare user data for creation (sets defaults)."""
    user_data["created_at"] = datetime.now()
    user_data["status"] = "active"
    return user_data

def validate_user(user_data):
    """Validate user data. Raises ValueError if invalid."""
    if not user_data.get("email"):
        raise ValueError("email required")

def is_authenticated(request):
    """Check if request has valid auth token. Pure predicate."""
    token = request.headers.get("Authorization")
    return token is not None and verify_token(token)
```

---

## Why naming contract violations matter

- **Code becomes misleading** — names are the first thing developers read. Broken contracts create false expectations.
- **AI generators are inconsistent with naming** — LLMs may generate a `validate_*` function that actually transforms data.
- **Review trust breaks down** — reviewers rely on names to quickly assess function purpose. Broken contracts hide bugs.
- **Refactoring becomes dangerous** — if `is_authenticated` has side effects, removing "unnecessary" calls can break authentication.

---

## How the score is calculated

NBV applies **naming pattern rules** to each function:

| Name prefix | Expected contract | Violation examples |
|---|---|---|
| `validate_*` | Must raise or return bool | Returns data, no conditional logic |
| `is_*`, `has_*` | Pure predicate (no side effects) | Modifies state, writes to DB |
| `get_*` | Returns value, doesn't modify | Deletes records, modifies input |
| `set_*` | Modifies target, returns None/self | Returns computed value |
| `check_*` | Raises or returns bool | Returns transformed data |

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix NBV findings

1. **Rename the function** to match its actual behavior.
2. **Or refactor the function** to match its name.
3. **Split mixed-responsibility functions** — if `validate_and_transform`, make separate `validate()` and `transform()`.
4. **Add docstrings** — explicitly document what the function does, especially if the name is intentionally broad.

---

## Configuration

```yaml
# drift.yaml
weights:
  naming_contract_violation: 0.04   # default weight (0.0 to 1.0)
```

---

## Detection details

1. **Parse all functions** from AST.
2. **Match function names** against naming pattern rules.
3. **Analyze function body** for contract-fulfilling behavior (raises, returns bool, state modification).
4. **Flag violations** where name implies a contract the body doesn't satisfy.

NBV is deterministic and AST-only.

---

## Related signals

- **PFS (Pattern Fragmentation)** — detects different approaches. NBV detects misnamed approaches.
- **EDS (Explainability Deficit)** — detects missing documentation. NBV detects misleading names.

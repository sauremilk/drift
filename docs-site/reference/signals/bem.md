# Broad Exception Monoculture Signal (BEM)

**Signal ID:** `BEM`  
**Full name:** Broad Exception Monoculture  
**Type:** Scoring signal (contributes to drift score)  
**Default weight:** `0.04`  
**Scope:** file_local

---

## What BEM detects

BEM detects modules where exception handling is **uniformly broad** — consistently catching `Exception`, `BaseException`, or using bare `except:` clauses — and uniformly swallowing errors. This is a proxy for "consistent wrongness": every handler follows the same bad pattern.

### Before — broad exception monoculture

```python
# services/data_pipeline.py
def fetch_data(url):
    try:
        response = requests.get(url)
        return response.json()
    except Exception:
        return None

def transform_data(data):
    try:
        return [item["value"] * 2 for item in data]
    except Exception:
        return []

def save_data(data, path):
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except Exception:
        pass
```

Every function catches `Exception` and silently swallows all errors. The module appears consistent, but it's consistently wrong.

### After — specific exception handling

```python
def fetch_data(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.warning("fetch failed", url=url, error=str(e))
        raise DataFetchError(url) from e

def transform_data(data):
    if not data:
        raise ValueError("empty data")
    return [item["value"] * 2 for item in data]

def save_data(data, path):
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except (OSError, TypeError) as e:
        raise DataSaveError(path) from e
```

---

## Why broad exception monoculture matters

- **Silent failures** — broad catches hide bugs, making them invisible until they compound.
- **AI code generators love bare except** — it's the easiest way to make code "not crash", which AI optimizes for.
- **Debugging becomes impossible** — when everything catches everything, stack traces and error messages are lost.
- **Masquerades as consistency** — the module looks "clean" because all handlers follow the same pattern. BEM specifically detects this false consistency.

---

## How the score is calculated

BEM evaluates the proportion of exception handlers in a module that use broad patterns:

1. **Count broad handlers** — `except Exception`, `except BaseException`, bare `except:`.
2. **Count total handlers** — all `try/except` blocks.
3. **Calculate monoculture ratio** — if ≥ 80% of handlers are broad, flag the module.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix BEM findings

1. **Replace broad catches with specific exceptions** — `requests.RequestException`, `ValueError`, `OSError`, etc.
2. **Log before swallowing** — if you must catch broadly at a boundary, log the full traceback.
3. **Propagate when appropriate** — not every exception should be caught locally.
4. **Add exception documentation** — document which exceptions each function can raise.

---

## Configuration

```yaml
# drift.yaml
weights:
  broad_exception_monoculture: 0.04   # default weight (0.0 to 1.0)
```

---

## Detection details

1. **Scan all `try/except` blocks** from AST.
2. **Classify each handler** — broad (Exception, BaseException, bare except) vs. specific.
3. **Calculate module-level monoculture ratio**.
4. **Flag modules** where broad handlers dominate.

BEM is deterministic and AST-only.

---

## Related signals

- **PFS (Pattern Fragmentation)** — detects inconsistent patterns. BEM detects consistently *bad* patterns.
- **ECM (Exception Contract Drift)** — detects changing exception behavior over time. BEM detects static exception quality.
- **GCD (Guard Clause Deficit)** — detects missing input validation. BEM detects poor error handling.

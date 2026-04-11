# Bypass Accumulation Signal (BAT)

**Signal ID:** `BAT`  
**Full name:** Bypass Accumulation  
**Type:** Scoring signal (contributes to drift score)  
**Default weight:** `0.03`  
**Scope:** file_local

---

## What BAT detects

BAT detects files where **quality-bypass markers accumulate** beyond a density threshold. These markers include `# type: ignore`, `# noqa`, `# pragma: no cover`, `typing.Any`, `cast()`, `@pytest.mark.skip`, and `TODO`/`FIXME` comments. Each marker is acceptable in isolation, but accumulation signals systemic quality evasion.

### Before — bypass accumulation

```python
from typing import Any, cast

def process(data: Any) -> Any:  # type: ignore[no-any-return]
    result = cast(dict, data)  # noqa: S101
    if result.get("value"):
        return result["value"]  # type: ignore
    return None  # pragma: no cover
    # TODO: handle edge cases
    # FIXME: this sometimes crashes
```

Seven bypass markers in a 10-line function. The code is more bypass than logic.

### After — addressed bypasses

```python
from typing import TypedDict

class ProcessInput(TypedDict):
    value: str | None

def process(data: ProcessInput) -> str | None:
    if data.get("value"):
        return data["value"]
    return None
```

---

## Why bypass accumulation matters

- **Each bypass is a deferred problem** — they represent conscious decisions to skip quality checks.
- **AI-generated code often needs bypasses** — type stubs are incomplete, so `# type: ignore` is common.
- **Accumulation signals systemic issues** — a file with one `noqa` is fine; a file with ten suggests the code doesn't fit the project's quality standards.
- **Quality drift is measurable** — BAT makes bypass density visible and trackable over time.

---

## How the score is calculated

BAT counts bypass markers and calculates density:

$$
\text{bypass\_density} = \frac{\text{bypass\_marker\_count}}{\text{total\_lines}}
$$

Files exceeding the density threshold are flagged.

**Tracked markers:**
- `# type: ignore` (with or without error codes)
- `# noqa` (with or without rule codes)
- `# pragma: no cover`
- `typing.Any` usage
- `cast()` calls
- `@pytest.mark.skip` / `@pytest.mark.xfail`
- `TODO` / `FIXME` / `HACK` / `XXX` comments

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix BAT findings

1. **Address the underlying issue** — each bypass exists for a reason. Fix the root cause.
2. **Add proper types** instead of `Any` and `cast()`.
3. **Fix linting issues** instead of adding `noqa`.
4. **Write tests** instead of `pragma: no cover`.
5. **Resolve TODOs** — if a TODO has been there for months, either do it or remove it.

---

## Configuration

```yaml
# drift.yaml
weights:
  bypass_accumulation: 0.03   # default weight (0.0 to 1.0)
```

---

## Detection details

1. **Scan all source lines** for known bypass markers (regex-based).
2. **Count markers per file** — total and by category.
3. **Calculate bypass density** (markers / total lines).
4. **Flag files** exceeding the density threshold.

BAT is deterministic and text-based (does not require AST parsing).

---

## Related signals

- **TPD (Test Polarity Deficit)** — detects incomplete tests. BAT detects skipped/incomplete quality checks.
- **BEM (Broad Exception Monoculture)** — detects poor error handling. BAT detects the markers that acknowledge poor quality.

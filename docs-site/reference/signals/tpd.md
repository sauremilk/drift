# Test Polarity Deficit Signal (TPD)

**Signal ID:** `TPD`  
**Full name:** Test Polarity Deficit  
**Type:** Scoring signal (contributes to drift score)  
**Default weight:** `0.04`  
**Scope:** file_local

---

## What TPD detects

TPD detects test suites that contain **only happy-path assertions** — tests that verify correct behavior but never test boundary conditions, error cases, or invalid inputs. A test suite that only checks "does it work?" without checking "does it fail correctly?" provides incomplete safety.

### Before — happy path only

```python
# tests/test_calculator.py
def test_add():
    assert add(2, 3) == 5

def test_subtract():
    assert subtract(10, 4) == 6

def test_multiply():
    assert multiply(3, 7) == 21
```

Three tests, all positive. No tests for divide-by-zero, overflow, or invalid inputs.

### After — balanced polarity

```python
def test_add():
    assert add(2, 3) == 5

def test_subtract():
    assert subtract(10, 4) == 6

def test_divide_by_zero():
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)

def test_add_invalid_type():
    with pytest.raises(TypeError):
        add("a", 3)

def test_multiply_overflow():
    assert multiply(MAX_INT, 2) == expected_overflow_result
```

---

## Why test polarity matters

- **False confidence** — 100% passing tests with only happy paths gives a false sense of security.
- **AI generates happy-path tests by default** — LLMs produce tests that verify the example output, not edge cases.
- **Bugs live in edge cases** — the most dangerous bugs are in error paths, boundary conditions, and unexpected inputs.
- **Regression risk** — without negative tests, error-handling changes can silently break without any test failure.

---

## How the score is calculated

TPD analyzes each test file for the presence of negative test indicators:

1. **Check for `pytest.raises`** — standard pytest error expectation.
2. **Check for `assertRaises`** — unittest-style error expectations.
3. **Check for boundary/edge-case assertions** — comparisons against zero, None, empty containers, limits.
4. **Calculate polarity ratio** — tests with negative assertions vs. total tests.

Modules where < 20% of tests have negative polarity are flagged.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix TPD findings

1. **Add error-case tests** — for each function, ask "what should happen with invalid input?"
2. **Use `pytest.raises`** — explicit error expectations are more readable than try/except in tests.
3. **Test boundary conditions** — empty lists, None, zero, maximum values.
4. **Follow the testing pyramid for polarity** — aim for ≥ 30% negative/boundary tests.

---

## Configuration

```yaml
# drift.yaml
weights:
  test_polarity_deficit: 0.04   # default weight (0.0 to 1.0)
```

---

## Detection details

1. **Identify test files** via naming conventions (`test_*.py`, `*_test.py`).
2. **Parse test functions** from AST.
3. **Scan for negative indicators** — `pytest.raises`, `assertRaises`, `with self.assertRaises`, exception-related assertions.
4. **Calculate polarity ratio** per test file.
5. **Flag test files** below the negative polarity threshold.

TPD is deterministic and AST-only.

---

## Related signals

- **EDS (Explainability Deficit)** — checks for test existence. TPD checks for test quality.
- **BAT (Bypass Accumulation)** — detects `@pytest.mark.skip` markers. TPD detects missing negative tests.

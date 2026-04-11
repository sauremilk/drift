# Exception Contract Drift Signal (ECM)

**Signal ID:** `ECM`  
**Full name:** Exception Contract Drift  
**Type:** Scoring signal (contributes to drift score)  
**Default weight:** `0.03`  
**Scope:** git_dependent

---

## What ECM detects

ECM detects public functions whose **exception profile changed across recent commits** while the function signature remained stable. When a function silently starts raising different exceptions (or stops raising ones it used to), callers break without any API change being visible.

### Example finding

```
exception_contract_drift in services/payment.py::process_payment
  Previous exceptions: [ValueError, PaymentError]
  Current exceptions: [ValueError, PaymentError, TimeoutError, ConnectionError]
  Signature: unchanged
  → New exceptions: TimeoutError, ConnectionError (added in commit abc123)
```

The function now raises two new exceptions that callers don't handle.

---

## Why exception contract drift matters

- **Silent API breakage** — the function signature doesn't change, but callers start seeing unexpected exceptions.
- **AI-generated changes** often modify exception paths without updating call sites.
- **Cascading failures** — new exceptions propagate through the call chain, causing crashes in unrelated code.
- **Testing blind spots** — tests written for the original exception profile miss the new ones.

---

## How the score is calculated

ECM compares exception profiles across git history:

1. **Extract current exception profile** — all `raise` statements and their exception types from AST.
2. **Extract previous exception profile** — same analysis on the last committed version.
3. **Compute difference** — new exceptions, removed exceptions, changed exception patterns.
4. **Score based on delta magnitude** — more changes = higher score.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix ECM findings

1. **Document the new exceptions** — add them to the docstring's Raises section.
2. **Update callers** — ensure all call sites handle the new exceptions.
3. **Consider wrapping** — if the new exceptions come from a dependency, wrap them in a domain-specific exception.
4. **Add tests** — write tests that verify both the old and new exception paths.

---

## Configuration

```yaml
# drift.yaml
weights:
  exception_contract_drift: 0.03   # default weight (0.0 to 1.0)
```

---

## Detection details

1. **Load git history** for modified files.
2. **Parse current AST** and **previous AST** (from last commit).
3. **Extract exception profiles** — `raise` statements, exception types, handler patterns.
4. **Diff profiles** — identify added, removed, changed exceptions.
5. **Score delta** per function.

ECM **requires git history** (`git_dependent=True`). Without a git repository, ECM produces no findings.

---

## Related signals

- **BEM (Broad Exception Monoculture)** — detects poor exception quality. ECM detects exception changes over time.
- **TVS (Temporal Volatility)** — detects volatile modules. ECM detects specific behavioral changes in exception handling.
- **CCC (Co-Change Coupling)** — also git-dependent. ECM focuses on exception-specific drift.

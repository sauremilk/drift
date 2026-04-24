# Mutant Duplicate Signal (MDS)

**Signal ID:** `MDS`
**Full name:** Mutant Duplicate Score
**Type:** Scoring signal (contributes to drift score)
**Default weight:** `0.13`
**Scope:** cross_file

---

## What MDS detects

MDS detects **near-duplicate functions** — functions that are structurally almost identical but differ in minor ways (renamed variables, slightly different logic). This is the classic "copy-paste-then-modify" anti-pattern, amplified by AI code generation where each session produces a slightly different variant.

### Before — mutant duplicates

```python
# utils/validation.py
def validate_email(email: str) -> bool:
    if not email or "@" not in email:
        return False
    parts = email.split("@")
    return len(parts) == 2 and len(parts[1]) > 0

# helpers/checks.py
def check_email_valid(mail: str) -> bool:
    if not mail or "@" not in mail:
        return False
    segments = mail.split("@")
    return len(segments) == 2 and len(segments[1]) > 0
```

Two functions with identical logic, different names and variable names — a mutant duplicate.

### After — consolidated

```python
# utils/validation.py
def validate_email(email: str) -> bool:
    if not email or "@" not in email:
        return False
    parts = email.split("@")
    return len(parts) == 2 and len(parts[1]) > 0

# helpers/checks.py — imports instead of duplicating
from utils.validation import validate_email
```

---

## Why mutant duplicates matter

- **Bug fixes applied once, not everywhere** — fixing a bug in one copy leaves the others vulnerable.
- **Divergence over time** — initially-identical functions drift apart as each gets modified independently.
- **AI generation is the primary cause** — LLMs generate functions from scratch each session, creating plausible but slightly different implementations.
- **Code review can't catch what looks correct** — each copy works in isolation; the problem is the redundancy.

---

## How the score is calculated

MDS uses a **hybrid similarity metric** combining:

1. **AST Jaccard similarity** — structural comparison of the abstract syntax tree (node types and patterns).
2. **Cosine embedding similarity** (optional) — semantic comparison using sentence-transformer embeddings.

$$
\text{similarity} = \alpha \cdot \text{AST\_Jaccard} + (1 - \alpha) \cdot \text{cosine\_embedding}
$$

Functions with similarity ≥ 0.80 (configurable) are flagged as mutant duplicates.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix MDS findings

1. **Choose the canonical implementation** — MDS reports which function has the higher quality (more tests, better documentation).
2. **Delete the duplicate** — remove the lesser copy and update all call sites to use the canonical version.
3. **Extract common logic** — if both functions have legitimate differences, extract the shared core into a base helper.
4. **Add an import** — replace the duplicate with an import from the canonical location.

---

## Configuration

```yaml
# drift.yaml
weights:
  mutant_duplicate: 0.13   # default weight (0.0 to 1.0)

thresholds:
  similarity_threshold: 0.80   # minimum similarity to flag (0.0 to 1.0)
  min_function_loc: 15         # skip functions shorter than this
```

Set `similarity_threshold` higher (e.g. 0.90) to reduce false positives. Set `min_function_loc` higher to ignore small utility functions.

---

## Detection details

1. **Collect all functions** with LOC ≥ `min_function_loc` from AST parsing.
2. **Compute pairwise similarity** using AST fingerprints (Jaccard index).
3. **Optionally enhance** with embedding similarity (when `embeddings_enabled: true`).
4. **Group into clusters** of mutant duplicates (transitively connected).
5. **Report cluster** with canonical candidate and all variants.

MDS is deterministic when embeddings are disabled. With embeddings, results may vary slightly based on model version.

---

## Related signals

- **PFS (Pattern Fragmentation)** — finds the same *intent* solved differently. MDS finds the same *code* duplicated. PFS and MDS can fire on the same module but for different reasons.
- **COD (Cohesion Deficit)** — finds modules with too many responsibilities. MDS finds specific function-level duplication.

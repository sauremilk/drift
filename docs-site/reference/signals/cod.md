# Cohesion Deficit Signal (COD)

**Signal ID:** `COD`  
**Full name:** Cohesion Deficit  
**Type:** Scoring signal (contributes to drift score)  
**Default weight:** `0.01`  
**Scope:** cross_file

---

## What COD detects

COD detects **"god modules"** — files containing many semantically unrelated responsibilities. When a file has functions that share little naming overlap, it's likely doing too many things at once. This is especially common in AI-generated code, where an LLM adds new functionality to the nearest available file.

### Before — low cohesion

```python
# utils.py
def validate_email(email): ...
def connect_database(url): ...
def format_currency(amount): ...
def resize_image(path, width): ...
def send_notification(user, message): ...
def parse_csv_headers(content): ...
```

Six functions with zero semantic overlap — a classic "utility dumping ground."

### After — cohesive modules

```python
# validation.py
def validate_email(email): ...
def validate_phone(phone): ...

# formatting.py
def format_currency(amount): ...
def format_date(dt): ...

# notifications.py
def send_notification(user, message): ...
```

---

## Why cohesion deficits matter

- **Change amplification** — any feature change might touch the god module, increasing merge conflicts.
- **Testing difficulty** — a test for one function requires importing unrelated dependencies.
- **AI grows god modules** — code assistants see the file and keep adding to it.
- **Ownership ambiguity** — no one team or developer owns the full module.

---

## How the score is calculated

COD uses **pairwise name-overlap (Jaccard similarity)** on function and class names within a file:

1. **Tokenize names** — split `validate_email` into `{validate, email}`.
2. **Compute pairwise Jaccard** — measure word overlap between all function name pairs.
3. **Average similarity** — lower average = lower cohesion = higher score.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix COD findings

1. **Split the module** — group related functions into separate files.
2. **Use the "single reason to change" rule** — each module should have one cohesive responsibility.
3. **Create a package** — replace `utils.py` with a `utils/` directory containing focused modules.
4. **Move incrementally** — introduce the new structure and migrate function by function.

---

## Configuration

```yaml
# drift.yaml
weights:
  cohesion_deficit: 0.01   # default weight (0.0 to 1.0)
```

---

## Detection details

1. **Parse all functions and classes** from AST.
2. **Tokenize names** using underscore/camelCase splitting.
3. **Compute pairwise Jaccard similarity** for all name pairs in the file.
4. **Average across all pairs** to get a cohesion score.
5. **Invert** — low cohesion = high deficit score.

COD is deterministic, AST-based, and uses no LLM calls.

---

## Related signals

- **MDS (Mutant Duplicates)** — detects duplicate functions. COD detects unrelated functions in the same file.
- **FOE (Fan-Out Explosion)** — detects files importing too many modules. COD detects files *containing* too many responsibilities.

# Dead Code Accumulation Signal (DCA)

**Signal ID:** `DCA`  
**Full name:** Dead Code Accumulation  
**Type:** Report-only signal (weight 0.0 — does not contribute to drift score)  
**Default weight:** `0.0`  
**Scope:** cross_file

---

## What DCA detects

DCA detects **exported functions and classes that are never imported elsewhere** in the project — potentially dead code that increases maintenance burden without providing value. This signal specifically targets accumulation, where many unused exports build up over time.

### Example finding

```
dead_code_accumulation in utils/legacy_helpers.py
  Unreferenced exports: 5/7 functions
  Functions: format_v1(), parse_old_config(), legacy_transform(), 
             convert_timestamp_v2(), render_old_template()
  → Score: 0.71 (HIGH)
```

### Before — unused exports accumulate

```python
# utils/legacy_helpers.py
def format_v1(data): ...          # unused after v2 migration
def parse_old_config(path): ...   # replaced by new config system
def legacy_transform(input): ...  # never called
def convert_timestamp_v2(ts): ... # superseded
def render_old_template(ctx): ... # replaced by Jinja2

def current_helper(x): ...       # actively used
def active_formatter(d): ...     # actively used
```

Five of seven functions are never imported anywhere.

---

## Why dead code accumulation matters

- **Maintenance cost** — dead code must still be understood, formatted, linted, and sometimes updated.
- **Confusion** — developers (and AI) may call dead code, not realizing it's abandoned.
- **AI generates more dead code** — each AI session may create functions that end up unused after iteration.
- **Test burden** — dead code either has tests (wasted effort) or no tests (coverage noise).
- **Security surface** — dead code may have vulnerabilities that remain unpatched because nobody realizes it's deployed.

---

## How the score is calculated

DCA builds a project-wide import/usage graph:

1. **Identify all exports** — public functions and classes (no `_` prefix) in each file.
2. **Build usage graph** — check which exports are imported or referenced by other files.
3. **Calculate unused ratio** — proportion of exports with zero external references.
4. **Score per module** — higher when more functions are unreferenced.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## Status

DCA is **report-only** (weight `0.0`) because of known false positive sources:
- **Dynamic imports** — `importlib.import_module()` or plugin systems.
- **Framework entry points** — Django views, Flask handlers, Click commands discovered at runtime.
- **Public API exports** — functions intended for external consumers, not internal use.

---

## How to fix DCA findings

1. **Verify the code is truly unused** — check for dynamic imports, `__all__` exports, framework registration.
2. **Delete confirmed dead code** — if it's in version control, you can always recover it.
3. **Mark intentionally unused code** — use `__all__` or comments to indicate public API.
4. **Schedule periodic cleanup** — dead code accumulates continuously; regular pruning is needed.

---

## Configuration

```yaml
# drift.yaml
weights:
  dead_code_accumulation: 0.0   # report-only (set > 0.0 to make scoring-active)
```

---

## Detection details

1. **Parse all source files** — extract function and class definitions.
2. **Filter to public exports** — exclude `_`-prefixed names.
3. **Build cross-file reference graph** — check import statements and name references.
4. **Identify unreferenced exports** — exports with zero cross-file references.
5. **Score per module** based on unused-to-total ratio.

DCA is deterministic and AST-based. Cross-file resolution requires parsing the entire project.

---

## Related signals

- **COD (Cohesion Deficit)** — detects god modules with many responsibilities. DCA detects modules with unused code.
- **PHR (Phantom Reference)** — detects references to nonexistent code. DCA detects existing code that's never referenced.

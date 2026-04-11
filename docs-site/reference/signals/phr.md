# Phantom Reference Signal (PHR)

**Signal ID:** `PHR`  
**Full name:** Phantom Reference  
**Type:** Scoring signal (contributes to drift score)  
**Default weight:** `0.02`  
**Scope:** cross_file

---

## What PHR detects

PHR detects **function calls, attribute accesses, and decorator references that cannot be resolved** against local or project-wide symbol tables. These are "hallucinated references" — code that calls functions or uses attributes that don't exist anywhere in the project. This is a direct consequence of AI code generation, where LLMs invent plausible-sounding APIs.

### Before — phantom references

```python
from services.auth import verify_token, require_permissions  # ← require_permissions doesn't exist
from utils.helpers import sanitize_html  # ← sanitize_html doesn't exist

@require_permissions("admin")  # ← phantom decorator
def admin_dashboard():
    data = get_dashboard_data()
    return sanitize_html(render_template(data))
```

The AI generated calls to functions that look right but don't exist in the codebase.

### After — resolved references

```python
from services.auth import verify_token, login_required  # ← actual function
from markupsafe import escape  # ← actual library

@login_required
def admin_dashboard():
    data = get_dashboard_data()
    return escape(render_template(data))
```

---

## Why phantom references matter

- **Runtime crashes** — `AttributeError` or `ImportError` at the worst possible time.
- **AI hallucination artifact** — LLMs generate function names that "should" exist based on naming patterns.
- **Hard to catch in review** — `require_permissions` looks correct. You'd need to check the import source to notice it doesn't exist.
- **Cascading failures** — phantom references may only trigger on specific code paths, causing intermittent production errors.

---

## How the score is calculated

PHR builds a project-wide symbol table and checks all references against it:

1. **Build symbol table** — all defined functions, classes, methods, and attributes across the project.
2. **Extract all references** — function calls, attribute accesses, decorator usages.
3. **Resolve references** — check each reference against the symbol table and installed packages.
4. **Flag unresolvable references** as phantom.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix PHR findings

1. **Replace with actual functions** — find the correct function name in the codebase.
2. **Create the missing function** — if the phantom reference describes needed functionality, implement it.
3. **Install missing packages** — if the reference is to an external library, add it to requirements.
4. **Remove dead code** — if the call path is unused, remove it entirely.

---

## Configuration

```yaml
# drift.yaml
weights:
  phantom_reference: 0.02   # default weight (0.0 to 1.0)
```

---

## Detection details

1. **Parse all source files** to build a comprehensive symbol table.
2. **Extract all call expressions, attribute accesses, and decorator references** from AST.
3. **Attempt resolution** — check against local scope, module scope, project scope, and installed packages.
4. **Flag unresolvable symbols** with context (file, line, reference type).

PHR is deterministic and AST-based. Cross-file resolution requires parsing the entire project.

---

## Related signals

- **DIA (Doc-Implementation Drift)** — detects documentation references that can't be resolved. PHR detects code references that can't be resolved.
- **AVS (Architecture Violation)** — detects wrong imports. PHR detects imports/references to nonexistent symbols.

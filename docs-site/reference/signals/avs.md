# Architecture Violation Signal (AVS)

**Signal ID:** `AVS`  
**Full name:** Architecture Violation Score  
**Type:** Scoring signal (contributes to drift score)  
**Default weight:** `0.16`  
**Scope:** cross_file

---

## What AVS detects

AVS detects imports that cross **layer boundaries** — for example, a route handler importing directly from a database module instead of going through a service layer. This is one of the strongest indicators of architectural erosion, especially in projects where AI-generated code bypasses established module hierarchies.

### Before — layer violation

```python
# routes/user_routes.py
from database.models import User          # ← direct DB access from route layer
from database.connection import get_db    # ← bypasses service layer

@app.get("/users/{user_id}")
def get_user(user_id: int):
    db = get_db()
    return db.query(User).get(user_id)
```

The route handler directly accesses the database layer, skipping the service layer entirely.

### After — respecting layer boundaries

```python
# routes/user_routes.py
from services.user_service import get_user_by_id   # ← proper service call

@app.get("/users/{user_id}")
def get_user(user_id: int):
    return get_user_by_id(user_id)
```

Access goes through the service layer, maintaining separation of concerns.

---

## Why architecture violations matter

- **Coupling explosion** — direct cross-layer imports create hidden dependencies that make refactoring dangerous.
- **Testing difficulty** — route tests need database fixtures instead of simple service mocks.
- **AI generation amplifies violations** — LLMs often produce the shortest working path, ignoring project-specific layer conventions.
- **Erosion is gradual** — each violation makes the next one more likely, as developers copy existing patterns.

---

## How the score is calculated

AVS evaluates each import statement against configured layer boundary policies. The score combines:

1. **Violation count** per module — more violations indicate systemic disregard for boundaries.
2. **Layer distance** — imports skipping multiple layers score higher than adjacent-layer violations.
3. **Hub dampening** — modules that serve as intentional "hubs" (many importers) receive dampened scores to avoid false positives.
4. **Omnilayer recognition** — directories configured as `omnilayer_dirs` (allowed to be imported everywhere) are excluded.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix AVS findings

1. **Introduce a service layer** — if routes directly access the database, create service functions that mediate.
2. **Respect the import direction** — lower layers should not import from higher layers.
3. **Configure omnilayer directories** — for shared utilities that are intentionally available everywhere, add them to `omnilayer_dirs`.
4. **Use dependency injection** — pass dependencies through function arguments rather than hard-coded imports.

---

## Configuration

```yaml
# drift.yaml
weights:
  architecture_violation: 0.16   # default weight (0.0 to 1.0)

policies:
  layer_boundaries:
    - name: "strict_layers"
      from: "routes/**"
      deny_import: ["database/**", "infrastructure/**"]
  omnilayer_dirs: ["src/common/", "src/shared/"]
```

Set weight to `0.0` to disable AVS scoring entirely. Use `policies.layer_boundaries` to define project-specific rules. Use `omnilayer_dirs` for legitimately shared code.

---

## Detection details

AVS uses the following algorithm:

1. **Parse all imports** from AST across the project.
2. **Resolve import targets** to physical file paths.
3. **Match against configured layer boundary policies** (deny rules).
4. **Apply hub dampening** for high-fan-in modules.
5. **Apply embedding-based layer inference** (optional) to infer layer relationships when no explicit policy exists.

AVS is deterministic, AST-based, and works with or without explicit policy configuration. When no policies are configured, it uses heuristic directory-name analysis to infer layer relationships.

---

## Related signals

- **PFS (Pattern Fragmentation)** — detects inconsistent implementations. AVS finds import-level boundary crossings; PFS finds behavioral inconsistency.
- **CCC (Co-Change Coupling)** — detects hidden coupling through commit history. AVS finds static import violations; CCC finds dynamic coupling.
- **CIR (Circular Import)** — detects import cycles. AVS finds directional violations; CIR finds circular dependencies.

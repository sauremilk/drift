# Missing Authorization Signal (MAZ)

**Signal ID:** `MAZ`  
**Full name:** Missing Authorization  
**Type:** Scoring signal (contributes to drift score)  
**Default weight:** `0.02`  
**Scope:** file_local

---

## What MAZ detects

MAZ detects **API endpoints lacking authorization checks** — routes that handle user requests without verifying permissions. This targets the classic "vibe-coding security gap" where AI-generated endpoints are functional but miss access control. Maps to **CWE-862: Missing Authorization**.

### Before — no authorization

```python
@app.route("/api/admin/users", methods=["DELETE"])
def delete_user():
    user_id = request.json["user_id"]
    db.session.delete(User.query.get(user_id))
    db.session.commit()
    return {"status": "deleted"}
```

An admin-only endpoint with zero authorization checks.

### After — with authorization

```python
@app.route("/api/admin/users", methods=["DELETE"])
@require_role("admin")
def delete_user():
    user_id = request.json["user_id"]
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return {"status": "deleted"}
```

---

## Why missing authorization matters

- **CWE-862** is consistently in the OWASP Top 10 — broken access control is the #1 web vulnerability.
- **AI generates functional code, not secure code** — endpoint handlers from AI assistants rarely include auth decorators unless prompted.
- **One missing check = full privilege escalation** — a single unprotected admin endpoint compromises the entire application.
- **Easy to miss in review** — endpoints often look correct when reviewing logic; the missing decorator is a negative signal (absence, not presence).

---

## How the score is calculated

MAZ checks each detected endpoint for authorization indicators:

1. **Detect endpoints** — `@app.route`, `@router.get`, FastAPI path decorators, Django URL patterns.
2. **Check for auth decorators** — `@login_required`, `@require_role`, `@authenticated`, `@permission_required`, etc.
3. **Check for body-level auth** — `current_user`, `request.user`, permission checks in function body.
4. **Check for class-level auth** — `LoginRequiredMixin`, `PermissionRequiredMixin`, class-level decorators.
5. **Flag endpoints** with no authorization indicator.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix MAZ findings

1. **Add an auth decorator** — the simplest and most visible approach.
2. **Use class-based views with auth mixins** — for consistent auth across a view group.
3. **Add middleware** — for blanket auth requirements (with explicit public route exceptions).
4. **Document intentionally public endpoints** — use a `@public` or `@no_auth_required` marker.

---

## Configuration

```yaml
# drift.yaml
weights:
  missing_authorization: 0.02   # default weight (0.0 to 1.0)
```

---

## Detection details

1. **Identify route handler functions** via decorator patterns.
2. **Scan decorators** for authorization-related names.
3. **Scan function body** for auth variable access.
4. **Scan class hierarchy** for auth mixins.
5. **Flag handlers** with no auth indicator.

MAZ is deterministic and AST-only.

---

## Related signals

- **ISD (Insecure Default)** — detects insecure configurations. MAZ detects missing access control in code.
- **HSC (Hardcoded Secret)** — detects credential exposure. MAZ detects missing auth enforcement.

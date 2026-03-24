# Demo Project — Intentional Architectural Drift

A minimal Python project with intentional drift patterns for testing and demonstration.

## Run drift on this project

```bash
pip install drift-analyzer
drift analyze --repo .
```

## What drift should find

| Signal | What's wrong | Where |
|--------|-------------|-------|
| PFS | Error handling implemented 3 different ways | `services/user_service.py`, `services/order_service.py`, `services/email_service.py` |
| AVS | DB import in API layer | `api/routes.py` |
| MDS | Near-identical validation functions | `utils/validators.py` |

These patterns are intentional — they illustrate what happens when multiple contributors (or AI code generators) implement the same concern independently.

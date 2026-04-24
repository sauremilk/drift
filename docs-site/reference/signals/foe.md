# Fan-Out Explosion Signal (FOE)

**Signal ID:** `FOE`
**Full name:** Fan-Out Explosion
**Type:** Scoring signal (contributes to drift score)
**Default weight:** `0.005`
**Scope:** file_local

---

## What FOE detects

FOE detects files importing an **excessive number of unique modules**, identifying emerging "god files" and central coupling hubs. High fan-out means that a change to any one of the imported modules may break this file.

### Before — fan-out explosion

```python
# services/order_service.py
from database.models import Order, User, Product, Inventory
from services.pricing import calculate_price
from services.tax import calculate_tax
from services.shipping import get_shipping_rate
from services.discount import apply_discount
from services.notification import send_order_email
from services.audit import log_transaction
from services.analytics import track_order_event
from services.payment import process_payment
from services.inventory import update_stock
from utils.validation import validate_order
from utils.formatting import format_receipt
from config import settings
```

13 unique import sources — this file depends on the entire application.

### After — reduced fan-out

```python
# services/order_service.py
from services.order_pipeline import OrderPipeline
from database.models import Order

def create_order(data):
    pipeline = OrderPipeline(data)
    return pipeline.execute()
```

Introduce a facade or pipeline to consolidate dependencies.

---

## Why fan-out explosion matters

- **Fragility** — any change to any imported module may require changes here.
- **Testing complexity** — testing requires mocking many dependencies.
- **Build time impact** — high fan-out creates long dependency chains.
- **AI compounds the problem** — code assistants add imports to solve immediate tasks without considering overall coupling.

---

## How the score is calculated

FOE counts unique import sources per file:

1. **Count unique imported modules** — each distinct top-level import source.
2. **Exclude barrel/index files** — `__init__.py` files with re-exports are excluded.
3. **Compare to threshold** — files exceeding the fan-out threshold are flagged.

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix FOE findings

1. **Introduce facade patterns** — create intermediate modules that aggregate related imports.
2. **Use dependency injection** — pass dependencies as arguments rather than importing them directly.
3. **Split the module** — a file needing 15 imports likely has too many responsibilities.
4. **Review necessity** — some imports may be unused or superseded.

---

## Configuration

```yaml
# drift.yaml
weights:
  fan_out_explosion: 0.005   # default weight (0.0 to 1.0)
```

---

## Detection details

1. **Parse all import statements** from AST.
2. **Normalize to unique source modules** — `from x.y import a, b` counts as one source.
3. **Exclude barrel files** (`__init__.py` with only re-exports).
4. **Count per file** and compare to threshold.

FOE is deterministic and AST-only.

---

## Related signals

- **COD (Cohesion Deficit)** — detects too many responsibilities. FOE detects too many dependencies.
- **AVS (Architecture Violation)** — detects wrong imports. FOE detects too many imports.

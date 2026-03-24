"""Order service — error handling variant 2: returns error dict."""

import logging

from db.models import Database

logger = logging.getLogger(__name__)


def place_order(user_id: int, items: list[str]) -> dict:
    db = Database("sqlite:///app.db")
    db.connect()
    try:
        db.execute(
            "INSERT INTO orders (user_id, items) VALUES (:uid, :items)",
            {"uid": user_id, "items": ",".join(items)},
        )
        return {"status": "ok", "user_id": user_id, "items": items}
    except Exception as exc:
        logger.error("Order failed for user %s: %s", user_id, exc)
        return {"status": "error", "message": str(exc)}


def cancel_order(order_id: int) -> dict:
    db = Database("sqlite:///app.db")
    db.connect()
    try:
        db.execute("DELETE FROM orders WHERE id = :id", {"id": order_id})
        return {"status": "ok", "cancelled": order_id}
    except Exception as exc:
        logger.error("Cancel failed for order %s: %s", order_id, exc)
        return {"status": "error", "message": str(exc)}

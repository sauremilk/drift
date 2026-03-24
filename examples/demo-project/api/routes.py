"""API routes — intentionally violates layer boundaries."""

# AVS: direct DB import in the API layer
from db.models import Database


def get_user_handler(user_id: int) -> dict:
    """Handle GET /users/{id} — reaches directly into DB layer."""
    db = Database("sqlite:///app.db")
    db.connect()
    user = db.get_user(user_id)
    if user is None:
        return {"error": "not found"}
    return user


def list_orders_handler(user_id: int) -> dict:
    """Handle GET /users/{id}/orders — also reaches into DB layer."""
    db = Database("sqlite:///app.db")
    db.connect()
    orders = db.get_orders(user_id)
    return {"orders": orders, "count": len(orders)}

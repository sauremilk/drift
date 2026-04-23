import type { Scenario } from './index';

/**
 * God Class scenario — a single class doing everything: database access,
 * user management, session handling, product/order management, payments,
 * email, caching, config, and metrics.
 *
 * Expected signals: PFS (pattern fragmentation), AVS (architecture violation)
 */
export const godClassScenario: Scenario = {
  id: 'god-class',
  label: 'God Class',
  description:
    'A class that does everything — violates the Single Responsibility Principle and concentrates architectural risk.',
  files: {
    'app_manager.py': `"""God class — manages database, users, sessions, products,
orders, payments, email, caching, config, and metrics in one place."""
import os
import json
import hashlib
import datetime
import logging
from typing import Any, Optional


class ApplicationManager:
    """Manages the entire application stack.

    Responsibilities: database, authentication, session management,
    product catalog, order processing, payment charging, email delivery,
    cache, configuration, and runtime metrics.
    """

    def __init__(self) -> None:
        # Database
        self.db_host = "localhost"
        self.db_port = 5432
        self.db_name = "appdb"
        self.db_user = "admin"
        self.db_password = "secret"  # noqa: S105  # pragma: allowlist secret
        self.db_connection: Any = None

        # Runtime state
        self.cache: dict[str, Any] = {}
        self.users: list[dict[str, Any]] = []
        self.products: list[dict[str, Any]] = []
        self.orders: list[dict[str, Any]] = []
        self.sessions: dict[str, Any] = {}

        # External services
        self.email_host = "smtp.example.com"
        self.payment_gateway = "stripe"
        self.logger = logging.getLogger(__name__)
        self.config: dict[str, Any] = {}
        self.metrics: dict[str, Any] = {}

    # ── Database ────────────────────────────────────────────────────────────

    def connect_db(self) -> None:
        self.logger.info("Connecting to database %s:%s", self.db_host, self.db_port)

    def disconnect_db(self) -> None:
        if self.db_connection:
            self.db_connection = None

    def execute_query(self, sql: str, params: Optional[list[Any]] = None) -> list[Any]:
        self.logger.debug("SQL: %s params=%s", sql, params)
        return []

    def fetch_all(self, sql: str) -> list[Any]:
        return self.execute_query(sql)

    def fetch_one(self, sql: str, params: Optional[list[Any]] = None) -> Optional[Any]:
        results = self.execute_query(sql, params)
        return results[0] if results else None

    # ── User management ─────────────────────────────────────────────────────

    def create_user(self, username: str, email: str, password: str) -> dict[str, Any]:
        hashed = hashlib.sha256(password.encode()).hexdigest()
        user = {"id": len(self.users) + 1, "username": username,
                "email": email, "password": hashed}
        self.users.append(user)
        self.cache_set(f"user:{user['id']}", user)
        return user

    def get_user(self, user_id: int) -> Optional[dict[str, Any]]:
        cached = self.cache_get(f"user:{user_id}")
        if cached:
            return cached  # type: ignore[return-value]
        return next((u for u in self.users if u["id"] == user_id), None)

    def update_user(self, user_id: int, data: dict[str, Any]) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        user.update(data)
        self.cache_set(f"user:{user_id}", user)
        return True

    def delete_user(self, user_id: int) -> None:
        self.users = [u for u in self.users if u["id"] != user_id]
        self.cache.pop(f"user:{user_id}", None)

    def authenticate_user(self, username: str, password: str) -> bool:
        hashed = hashlib.sha256(password.encode()).hexdigest()
        return any(
            u["username"] == username and u["password"] == hashed
            for u in self.users
        )

    def reset_password(self, email: str) -> str:
        token = hashlib.md5(email.encode()).hexdigest()  # noqa: S324
        self.send_email(email, "Password Reset", f"Your token: {token}")
        return token

    # ── Session management ───────────────────────────────────────────────────

    def create_session(self, user_id: int) -> str:
        sid = hashlib.sha256(str(datetime.datetime.now()).encode()).hexdigest()
        self.sessions[sid] = {"user_id": user_id, "created": str(datetime.datetime.now())}
        return sid

    def validate_session(self, session_id: str) -> bool:
        return session_id in self.sessions

    def destroy_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)

    def get_session_user(self, session_id: str) -> Optional[dict[str, Any]]:
        session = self.sessions.get(session_id)
        return self.get_user(session["user_id"]) if session else None

    # ── Product catalog ──────────────────────────────────────────────────────

    def add_product(self, name: str, price: float, stock: int) -> dict[str, Any]:
        product = {"id": len(self.products) + 1, "name": name,
                   "price": price, "stock": stock}
        self.products.append(product)
        return product

    def get_product(self, product_id: int) -> Optional[dict[str, Any]]:
        return next((p for p in self.products if p["id"] == product_id), None)

    def update_product_price(self, product_id: int, new_price: float) -> bool:
        product = self.get_product(product_id)
        if not product:
            return False
        product["price"] = new_price
        return True

    def update_stock(self, product_id: int, quantity: int) -> None:
        product = self.get_product(product_id)
        if product:
            product["stock"] += quantity

    def list_products(self, in_stock_only: bool = False) -> list[dict[str, Any]]:
        if in_stock_only:
            return [p for p in self.products if p["stock"] > 0]
        return list(self.products)

    # ── Order management ─────────────────────────────────────────────────────

    def create_order(self, user_id: int, product_ids: list[int]) -> dict[str, Any]:
        products = [self.get_product(pid) for pid in product_ids]
        total = sum(p["price"] for p in products if p)
        order = {"id": len(self.orders) + 1, "user_id": user_id,
                 "product_ids": product_ids, "total": total, "status": "pending"}
        self.orders.append(order)
        return order

    def process_payment(self, order_id: int, card_number: str) -> bool:
        order = next((o for o in self.orders if o["id"] == order_id), None)
        if not order:
            return False
        charged = self.charge_card(card_number, order["total"])
        if charged:
            order["status"] = "paid"
            self.send_order_confirmation(order)
        return charged

    def charge_card(self, card_number: str, amount: float) -> bool:
        # Direct payment logic — should live in a PaymentService
        self.logger.info("Charging card %s*** for %.2f", card_number[:4], amount)
        self.record_metric("payments_processed", amount)
        return True

    def refund_order(self, order_id: int) -> bool:
        order = next((o for o in self.orders if o["id"] == order_id), None)
        if order and order["status"] == "paid":
            order["status"] = "refunded"
            return True
        return False

    def get_order_history(self, user_id: int) -> list[dict[str, Any]]:
        return [o for o in self.orders if o["user_id"] == user_id]

    # ── Email ────────────────────────────────────────────────────────────────

    def send_email(self, to: str, subject: str, body: str) -> None:
        self.logger.info("Email → %s | %s", to, subject)

    def send_order_confirmation(self, order: dict[str, Any]) -> None:
        user = self.get_user(order["user_id"])
        if user:
            self.send_email(
                user["email"], "Order Confirmed",
                f"Order #{order['id']} total: \${order['total']:.2f}",
            )

    def send_bulk_email(self, template: dict[str, str]) -> None:
        for user in self.users:
            self.send_email(user["email"], template["subject"], template["body"])

    # ── Cache ────────────────────────────────────────────────────────────────

    def cache_get(self, key: str) -> Optional[Any]:
        return self.cache.get(key)

    def cache_set(self, key: str, value: Any, ttl: int = 300) -> None:
        _ = ttl  # TTL not enforced in this implementation
        self.cache[key] = value

    def cache_delete(self, key: str) -> None:
        self.cache.pop(key, None)

    def cache_clear(self) -> None:
        self.cache.clear()

    # ── Config ───────────────────────────────────────────────────────────────

    def load_config(self, path: str) -> None:
        with open(path) as fh:
            self.config = json.load(fh)

    def get_config(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    # ── Reporting ────────────────────────────────────────────────────────────

    def generate_sales_report(self) -> list[dict[str, Any]]:
        return [o for o in self.orders if o["status"] == "paid"]

    def generate_user_report(self) -> dict[str, Any]:
        return {"total_users": len(self.users), "active_sessions": len(self.sessions)}

    def export_to_csv(self, data: list[dict[str, Any]], filename: str) -> None:
        import csv
        if not data:
            return
        with open(filename, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(data[0].keys()))
            writer.writeheader()
            writer.writerows(data)

    # ── Metrics ──────────────────────────────────────────────────────────────

    def record_metric(self, name: str, value: Any) -> None:
        self.metrics[name] = value

    def get_metrics(self) -> dict[str, Any]:
        return dict(self.metrics)

    def setup_logging(self, level: str = "INFO") -> None:
        logging.basicConfig(level=getattr(logging, level))

    # ── Utility ──────────────────────────────────────────────────────────────

    def health_check(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "users": len(self.users),
            "products": len(self.products),
            "orders": len(self.orders),
            "cache_size": len(self.cache),
        }


class LegacyDataHelper:
    """Old helper class — duplicates hashing logic from ApplicationManager."""

    def hash_value(self, value: str) -> str:
        # Duplicate of ApplicationManager.create_user hashing
        return hashlib.sha256(value.encode()).hexdigest()

    def md5_token(self, value: str) -> str:
        # Duplicate of ApplicationManager.reset_password token generation
        return hashlib.md5(value.encode()).hexdigest()  # noqa: S324

    def process(self, data: Any) -> Optional[dict[str, Any]]:
        result: dict[str, Any] = {}
        if not isinstance(data, dict):
            return None
        for k, v in data.items():
            if v is None:
                continue
            if isinstance(v, str):
                result[k] = v.strip()
            elif isinstance(v, (int, float)):
                result[k] = v
            elif isinstance(v, list):
                result[k] = [x for x in v if x is not None]
            elif isinstance(v, dict):
                result[k] = self.process(v)
            else:
                result[k] = str(v)
        return result or None


# Module-level singleton — creates tight coupling for callers
manager = ApplicationManager()
`,
    'legacy_helper.py': `"""Legacy helper module — partial duplicate of logic in app_manager.py."""
import hashlib
import datetime
from typing import Optional


def hash_password(password: str) -> str:
    """Duplicates ApplicationManager.create_user password hashing."""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_token(data: str) -> str:
    """Duplicates ApplicationManager.reset_password token logic."""
    return hashlib.md5(data.encode()).hexdigest()  # noqa: S324


def create_timestamp() -> str:
    return datetime.datetime.now().isoformat()


def validate_email(email: str) -> bool:
    return "@" in email and "." in email


class QuickAuth:
    """Partially duplicates ApplicationManager authentication."""

    def check_password(self, raw: str, stored_hash: str) -> bool:
        return hashlib.sha256(raw.encode()).hexdigest() == stored_hash

    def make_session_token(self, user_id: int) -> str:
        return hashlib.sha256(f"{user_id}{datetime.datetime.now()}".encode()).hexdigest()

    def is_valid_email(self, email: str) -> Optional[bool]:
        if not email:
            return None
        return "@" in email
`,
  },
};

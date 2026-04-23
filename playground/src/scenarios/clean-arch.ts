import type { Scenario } from './index';

/**
 * Clean Architecture scenario — well-structured layered code:
 * models → services → api, with no cross-layer violations and no cycles.
 *
 * Expected: low drift score, mostly green heatmap.
 */
export const cleanArchScenario: Scenario = {
  id: 'clean-arch',
  label: 'Clean Architecture',
  description:
    'A properly layered codebase: pure models, focused services, thin API layer — no violations, no cycles.',
  files: {
    'models.py': `"""Pure data models — no business logic, no framework imports, no I/O."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """Represents a registered user."""

    id: int
    username: str
    email: str
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True


@dataclass
class Product:
    """A product in the catalog."""

    id: int
    name: str
    price: float
    stock: int
    description: str = ""


@dataclass
class OrderLine:
    """A single line item within an order."""

    product_id: int
    quantity: int
    unit_price: float

    @property
    def subtotal(self) -> float:
        return self.quantity * self.unit_price


@dataclass
class Order:
    """A customer order."""

    id: int
    user_id: int
    lines: list[OrderLine]
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def total(self) -> float:
        return sum(line.subtotal for line in self.lines)
`,
    'services.py': `"""Business logic layer — imports only from models, no framework dependencies."""
from datetime import datetime
from typing import Optional

from models import Order, OrderLine, Product, User


class UserService:
    """Handles user lifecycle operations."""

    def __init__(self) -> None:
        self._store: dict[int, User] = {}
        self._next_id = 1

    def create(self, username: str, email: str) -> User:
        user = User(id=self._next_id, username=username, email=email)
        self._store[user.id] = user
        self._next_id += 1
        return user

    def get(self, user_id: int) -> Optional[User]:
        return self._store.get(user_id)

    def deactivate(self, user_id: int) -> bool:
        user = self._store.get(user_id)
        if not user:
            return False
        user.is_active = False
        return True

    def list_active(self) -> list[User]:
        return [u for u in self._store.values() if u.is_active]


class ProductService:
    """Manages the product catalog."""

    def __init__(self) -> None:
        self._store: dict[int, Product] = {}
        self._next_id = 1

    def add(self, name: str, price: float, stock: int, description: str = "") -> Product:
        product = Product(id=self._next_id, name=name, price=price,
                          stock=stock, description=description)
        self._store[product.id] = product
        self._next_id += 1
        return product

    def get(self, product_id: int) -> Optional[Product]:
        return self._store.get(product_id)

    def reserve_stock(self, product_id: int, quantity: int) -> bool:
        product = self._store.get(product_id)
        if not product or product.stock < quantity:
            return False
        product.stock -= quantity
        return True

    def list_available(self) -> list[Product]:
        return [p for p in self._store.values() if p.stock > 0]


class OrderService:
    """Creates and tracks orders; depends on UserService and ProductService."""

    def __init__(self, users: UserService, products: ProductService) -> None:
        self._orders: dict[int, Order] = {}
        self._users = users
        self._products = products
        self._next_id = 1

    def place(self, user_id: int, cart: list[tuple[int, int]]) -> Optional[Order]:
        """Place an order. cart is a list of (product_id, quantity) pairs."""
        if not self._users.get(user_id):
            return None

        lines: list[OrderLine] = []
        for product_id, qty in cart:
            product = self._products.get(product_id)
            if not product:
                return None
            if not self._products.reserve_stock(product_id, qty):
                return None
            lines.append(OrderLine(product_id=product_id, quantity=qty,
                                   unit_price=product.price))

        order = Order(id=self._next_id, user_id=user_id, lines=lines)
        self._orders[order.id] = order
        self._next_id += 1
        return order

    def confirm(self, order_id: int) -> bool:
        order = self._orders.get(order_id)
        if not order or order.status != "pending":
            return False
        order.status = "confirmed"
        return True

    def get(self, order_id: int) -> Optional[Order]:
        return self._orders.get(order_id)

    def for_user(self, user_id: int) -> list[Order]:
        return [o for o in self._orders.values() if o.user_id == user_id]
`,
    'api.py': `"""Thin API layer — orchestrates services and translates to/from plain dicts.

Imports only from services; never from models directly (enforces layer boundary).
"""
from typing import Optional

from services import OrderService, ProductService, UserService

# Dependency injection at module level (swappable in tests)
users = UserService()
products = ProductService()
orders = OrderService(users, products)


# ── User endpoints ────────────────────────────────────────────────────────────

def register_user(username: str, email: str) -> dict:
    user = users.create(username, email)
    return {"id": user.id, "username": user.username, "email": user.email}


def get_user(user_id: int) -> Optional[dict]:
    user = users.get(user_id)
    if not user:
        return None
    return {"id": user.id, "username": user.username,
            "email": user.email, "is_active": user.is_active}


# ── Product endpoints ─────────────────────────────────────────────────────────

def add_product(name: str, price: float, stock: int, description: str = "") -> dict:
    product = products.add(name, price, stock, description)
    return {"id": product.id, "name": product.name,
            "price": product.price, "stock": product.stock}


def list_products() -> list[dict]:
    return [
        {"id": p.id, "name": p.name, "price": p.price, "stock": p.stock}
        for p in products.list_available()
    ]


# ── Order endpoints ───────────────────────────────────────────────────────────

def place_order(user_id: int, cart: list[dict]) -> Optional[dict]:
    """cart: list of {product_id, quantity}"""
    pairs = [(item["product_id"], item["quantity"]) for item in cart]
    order = orders.place(user_id, pairs)
    if not order:
        return None
    return {"id": order.id, "user_id": order.user_id,
            "total": order.total, "status": order.status}


def confirm_order(order_id: int) -> bool:
    return orders.confirm(order_id)


def get_order_history(user_id: int) -> list[dict]:
    return [
        {"id": o.id, "total": o.total, "status": o.status,
         "created_at": o.created_at.isoformat()}
        for o in orders.for_user(user_id)
    ]
`,
    'utils.py': `"""Shared pure-utility functions — no imports from other project modules."""
import json
from typing import Any


def to_json(obj: Any, *, indent: int = 2) -> str:
    """Serialize obj to a JSON string."""
    return json.dumps(obj, default=str, indent=indent)


def from_json(s: str) -> Any:
    """Deserialize a JSON string."""
    return json.loads(s)


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value to [lo, hi]."""
    return max(lo, min(hi, value))


def chunk(lst: list, size: int) -> list[list]:
    """Split lst into sub-lists of at most size elements."""
    return [lst[i : i + size] for i in range(0, len(lst), size)]


def flatten(nested: list[list]) -> list:
    """Flatten one level of nesting."""
    return [item for sublist in nested for item in sublist]
`,
  },
};

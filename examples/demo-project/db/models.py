"""Database connection and query helpers."""


class Database:
    """Simple database abstraction."""

    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def execute(self, query: str, params: dict | None = None) -> list[dict]:
        if not self._connected:
            raise RuntimeError("Not connected")
        return []

    def get_user(self, user_id: int) -> dict | None:
        rows = self.execute("SELECT * FROM users WHERE id = :id", {"id": user_id})
        return rows[0] if rows else None

    def get_orders(self, user_id: int) -> list[dict]:
        return self.execute(
            "SELECT * FROM orders WHERE user_id = :uid", {"uid": user_id}
        )

"""User service — error handling variant 1: bare try/except with print."""

from db.models import Database


def create_user(name: str, email: str) -> dict | None:
    db = Database("sqlite:///app.db")
    db.connect()
    try:
        db.execute(
            "INSERT INTO users (name, email) VALUES (:n, :e)",
            {"n": name, "e": email},
        )
        return {"name": name, "email": email}
    except Exception:
        print(f"Failed to create user {name}")
        return None


def delete_user(user_id: int) -> bool:
    db = Database("sqlite:///app.db")
    db.connect()
    try:
        db.execute("DELETE FROM users WHERE id = :id", {"id": user_id})
        return True
    except Exception:
        print(f"Failed to delete user {user_id}")
        return False

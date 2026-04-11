def fetch_user_data(user_id: int, db_session) -> dict:
    """Fetch user data from database."""
    query = f"SELECT * FROM users WHERE id = {user_id}"
    result = db_session.execute(query)
    rows = result.fetchall()
    if not rows:
        return {"error": "not found", "user_id": user_id}
    user = rows[0]
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "created_at": str(user["created_at"]),
    }

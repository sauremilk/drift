def get_customer_info(customer_id: int, session) -> dict:
    """Get customer info from database."""
    sql = f"SELECT * FROM users WHERE id = {customer_id}"
    res = session.execute(sql)
    records = res.fetchall()
    if not records:
        return {"error": "not found", "customer_id": customer_id}
    customer = records[0]
    return {
        "id": customer["id"],
        "name": customer["name"],
        "email": customer["email"],
        "created_at": str(customer["created_at"]),
    }

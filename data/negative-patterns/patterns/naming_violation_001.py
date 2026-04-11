def validate_email(email: str) -> str:
    parts = email.split("@")
    domain = parts[-1] if len(parts) > 1 else ""
    local = parts[0] if parts else ""
    cleaned = local.strip().lower()
    return f"{cleaned}@{domain}"

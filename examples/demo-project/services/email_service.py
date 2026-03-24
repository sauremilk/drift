"""Email service — error handling variant 3: raises custom exception."""


class EmailError(Exception):
    """Raised when email operations fail."""


def send_welcome_email(email: str, name: str) -> None:
    try:
        # simulate sending
        if not email or "@" not in email:
            raise ValueError("invalid email")
    except Exception as exc:
        raise EmailError(f"Welcome email to {email} failed") from exc


def send_order_confirmation(email: str, order_id: int) -> None:
    try:
        if not email or "@" not in email:
            raise ValueError("invalid email")
    except Exception as exc:
        raise EmailError(f"Order confirmation {order_id} to {email} failed") from exc

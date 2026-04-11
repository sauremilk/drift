def format_money(amount: float, currency: str = "EUR") -> str:
    """Format a monetary amount with currency symbol."""
    if amount < 0:
        prefix = "-"
        amount = abs(amount)
    else:
        prefix = ""
    formatted = f"{amount:.2f}"
    parts = formatted.split(".")
    integer_part = parts[0]
    decimal_part = parts[1]
    return f"{prefix}{integer_part}.{decimal_part} {currency}"

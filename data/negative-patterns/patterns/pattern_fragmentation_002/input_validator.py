def validate_email(email: str) -> bool:
    try:
        if "@" not in email:
            raise ValueError("Invalid email")
        return True
    except ValueError as e:
        raise AppError(str(e)) from e

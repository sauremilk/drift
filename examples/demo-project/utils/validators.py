"""Validators — near-identical implementations (MDS: mutant duplicates)."""

import re


def validate_email(value: str) -> bool:
    """Validate email address format."""
    if not value or not isinstance(value, str):
        return False
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, value))


def check_email_valid(email: str) -> bool:
    """Check whether an email string is valid."""
    if not email or not isinstance(email, str):
        return False
    regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(regex, email))


def is_valid_email_address(addr: str) -> bool:
    """Return True if addr looks like a valid email."""
    if addr is None or not isinstance(addr, str):
        return False
    email_re = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(email_re, addr) is not None


def validate_username(name: str) -> bool:
    """Validate a username string."""
    if not name or not isinstance(name, str):
        return False
    return 3 <= len(name) <= 64 and name.isalnum()


def check_username(username: str) -> bool:
    """Check that a username is acceptable."""
    if not username or not isinstance(username, str):
        return False
    if len(username) < 3 or len(username) > 64:
        return False
    return username.isalnum()

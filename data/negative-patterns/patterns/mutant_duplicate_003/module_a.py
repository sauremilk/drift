import hashlib


def compute_hash(data: str, algorithm: str = "sha256") -> str:
    """Compute hash of data."""
    if algorithm == "sha256":
        return hashlib.sha256(data.encode()).hexdigest()
    elif algorithm == "md5":
        return hashlib.md5(data.encode()).hexdigest()
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

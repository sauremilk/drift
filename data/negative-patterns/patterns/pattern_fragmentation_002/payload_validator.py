def validate_payload(payload: dict) -> dict:
    try:
        if not isinstance(payload, dict):
            raise TypeError("payload must be dict")
        if "version" not in payload:
            raise KeyError("missing version")
        return payload
    except (TypeError, KeyError):
        return {}

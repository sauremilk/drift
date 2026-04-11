def validate_form(data: dict) -> dict:
    result = {"valid": True, "errors": []}
    if not data.get("name"):
        result["valid"] = False
        result["errors"].append("name required")
    return result

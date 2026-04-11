def run_pipeline(stages, context, config):
    for stage in stages:
        if stage["type"] == "filter":
            context = [c for c in context if stage["fn"](c)]
        elif stage["type"] == "map":
            context = [stage["fn"](c) for c in context]
        elif stage["type"] == "reduce":
            val = context[0]
            for c in context[1:]:
                val = stage["fn"](val, c)
            context = [val]
        elif stage["type"] == "sort":
            context = sorted(context, key=stage.get("key"))
        else:
            context = list(context)
    return context


def validate_schema(data, rules, strict):
    errors = []
    for key, rule in rules.items():
        val = data.get(key)
        if rule == "required" and val is None:
            errors.append(f"{key} is required")
        elif rule == "int" and not isinstance(val, int):
            errors.append(f"{key} must be int")
        elif rule == "str" and not isinstance(val, str):
            errors.append(f"{key} must be str")
        elif rule == "positive" and (not isinstance(val, (int, float)) or val <= 0):
            errors.append(f"{key} must be positive")
        else:
            pass
    if strict and errors:
        raise ValueError(errors)
    return errors


def build_response(result, headers, status):
    body = {}
    for key in result:
        if isinstance(result[key], list):
            body[key] = len(result[key])
        elif isinstance(result[key], dict):
            body[key] = list(result[key].keys())
        elif isinstance(result[key], str):
            body[key] = result[key][:100]
        else:
            body[key] = result[key]
    for h_key, h_val in headers.items():
        if h_key.startswith("X-"):
            body[f"header_{h_key}"] = h_val
    return {"status": status, "body": body}

def transform(data, schema, options):
    result = []
    for item in data:
        out = {}
        for key, spec in schema.items():
            val = item.get(key)
            if spec == "upper":
                out[key] = val.upper()
            elif spec == "lower":
                out[key] = val.lower()
            elif spec == "strip":
                out[key] = val.strip()
            else:
                out[key] = val
        if options.get("filter_key"):
            if out.get(options["filter_key"]):
                result.append(out)
        else:
            result.append(out)
    return result


def aggregate(records, dimensions, funcs):
    groups = {}
    for r in records:
        key = tuple(r.get(d) for d in dimensions)
        if key not in groups:
            groups[key] = []
        groups[key].append(r)
    out = []
    for key, rows in groups.items():
        entry = dict(zip(dimensions, key))
        for fn in funcs:
            vals = [r.get(fn, 0) for r in rows]
            if vals:
                entry[fn] = sum(vals) / len(vals)
        out.append(entry)
    return out


def export_report(data, columns, fmt):
    lines = []
    header = [str(c) for c in columns]
    lines.append(",".join(header))
    for row in data:
        cells = []
        for col in columns:
            val = row.get(col, "")
            if fmt == "quoted":
                cells.append(f'"{val}"')
            elif fmt == "raw":
                cells.append(str(val))
            else:
                cells.append(str(val).strip())
        lines.append(",".join(cells))
    return "\n".join(lines)

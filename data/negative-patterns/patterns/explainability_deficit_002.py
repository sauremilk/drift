def cross_correlate(datasets, filters, thresholds, output_mode):
    results = {}
    for ds_name, dataset in datasets.items():
        for record in dataset:
            for f_name, f_func in filters.items():
                if not f_func(record):
                    continue
                for threshold_name, threshold_val in thresholds.items():
                    val = record.get(threshold_name, 0)
                    if val >= threshold_val:
                        key = f"{ds_name}:{f_name}:{threshold_name}"
                        if key not in results:
                            results[key] = []
                        results[key].append(record)
    if output_mode == "count":
        return {k: len(v) for k, v in results.items()}
    elif output_mode == "first":
        return {k: v[0] for k, v in results.items() if v}
    return results

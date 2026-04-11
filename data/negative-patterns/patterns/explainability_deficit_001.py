def process_batch(items, config, retry_count=3, timeout=30):
    results = []
    for item in items:
        if item.get("type") == "A":
            if item.get("priority") > 5:
                results.append(handle_high_priority(item))
            elif item.get("status") == "pending":
                results.append(handle_pending(item))
            else:
                results.append(handle_default(item))
        elif item.get("type") == "B":
            if config.get("fast_mode"):
                results.append(fast_process(item))
            else:
                results.append(slow_process(item))
        else:
            if retry_count > 0:
                results.append(
                    process_batch([item], config, retry_count - 1)
                )
            else:
                results.append(None)
    return [r for r in results if r is not None]

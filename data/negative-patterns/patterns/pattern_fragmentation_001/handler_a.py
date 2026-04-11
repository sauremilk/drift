def handle_a(data):
    try:
        process(data)
    except ValueError as e:
        raise AppError(str(e)) from e

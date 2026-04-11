import sys


def handle_c(data):
    try:
        process(data)
    except Exception:
        print("error", file=sys.stderr)
        sys.exit(1)

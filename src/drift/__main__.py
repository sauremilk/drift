"""Allow running drift as a module: python -m drift."""

from drift.cli import safe_main

if __name__ == "__main__":
    safe_main()

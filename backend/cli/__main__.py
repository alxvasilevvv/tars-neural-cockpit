"""``python -m backend.cli`` entry shim."""

from .main import main

if __name__ == "__main__":
    raise SystemExit(main())

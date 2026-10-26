"""PyInstaller entry point for the headless warehouse service."""

from serial_vision.warehouse.server import main

if __name__ == "__main__":
    raise SystemExit(main())

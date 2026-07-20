"""PyInstaller entry point for the packaged desktop application."""

from automatic_print.app import run


if __name__ == "__main__":
    raise SystemExit(run())

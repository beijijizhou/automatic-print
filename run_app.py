"""PyInstaller entry point for the packaged desktop application."""

from automatic_print.app import run
from automatic_print.crash_logging import run_with_crash_logging


if __name__ == "__main__":
    raise SystemExit(run_with_crash_logging(run))

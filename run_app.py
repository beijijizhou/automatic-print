"""PyInstaller entry point for the packaged desktop application."""

from automatic_print.runtime.crash_logging import run_with_crash_logging


def _load_and_run() -> int:
    # Keep UI and native-library imports inside the crash guard.  Importing the
    # application above this point makes a missing packaged DLL look like a
    # silent Windows launch failure and prevents the startup log being written.
    from automatic_print.app import run
    return run()


def main() -> int:
    return run_with_crash_logging(_load_and_run)


if __name__ == "__main__":
    from multiprocessing import freeze_support
    freeze_support()
    raise SystemExit(main())

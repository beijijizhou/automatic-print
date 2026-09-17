from .runtime.crash_logging import run_with_crash_logging
from multiprocessing import freeze_support


def _load_and_run() -> int:
    # Source/developer launches use ``python -m automatic_print``.  Keep the
    # complete UI import inside the same crash guard as the packaged launcher.
    from .app import run
    return run()


def main() -> int:
    freeze_support()
    return run_with_crash_logging(_load_and_run)


if __name__ == "__main__":
    raise SystemExit(main())

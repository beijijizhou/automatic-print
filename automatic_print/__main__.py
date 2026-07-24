from .app import run
from .crash_logging import run_with_crash_logging


if __name__ == "__main__":
    raise SystemExit(run_with_crash_logging(run))

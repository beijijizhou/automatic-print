from .runtime.crash_logging import run_with_crash_logging
from multiprocessing import freeze_support
import sys


def _load_and_run() -> int:
    # Source/developer launches use ``python -m automatic_print``.  Keep the
    # complete UI import inside the same crash guard as the packaged launcher.
    if "--remote-command" in sys.argv:
        index = sys.argv.index("--remote-command")
        if index + 1 >= len(sys.argv):
            return 2
        from .automation.api.machine_commands.runner import run_command
        return run_command(sys.argv[index + 1])
    from .app import run
    return run()


def main() -> int:
    freeze_support()
    return run_with_crash_logging(_load_and_run)


if __name__ == "__main__":
    raise SystemExit(main())

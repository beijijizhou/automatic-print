"""No-window background entry point installed with AutomaticPrint."""

import os
from pathlib import Path

from .monitor import PrintExpMonitor


def main():
    lock = _single_instance_lock()
    if lock is None:
        return 0
    PrintExpMonitor().run()
    return 0


def _single_instance_lock():
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".automatic-print")
    try:
        target = root / "AutomaticPrint" / "printerexp-monitor.lock"
        target.parent.mkdir(parents=True, exist_ok=True)
        stream = target.open("a+b")
        stream.seek(0)
        if not stream.read(1):
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        return stream
    except (OSError, ImportError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())

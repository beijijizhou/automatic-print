"""Run the desktop app and restart it automatically when source files change."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
WATCHED_FOLDER = PROJECT_ROOT / "automatic_print"


def snapshot() -> dict[Path, int]:
    return {
        path: path.stat().st_mtime_ns
        for path in WATCHED_FOLDER.rglob("*.py")
        if path.is_file()
    }


def main() -> int:
    state = snapshot()
    print("Development mode: the app will restart when Python files change.")

    while True:
        process = subprocess.Popen([sys.executable, "-m", "automatic_print"])
        restart = False

        while process.poll() is None:
            time.sleep(0.5)
            new_state = snapshot()
            if new_state != state:
                state = new_state
                restart = True
                print("Code changed. Restarting the app…")
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                break

        if not restart:
            return process.returncode or 0


if __name__ == "__main__":
    raise SystemExit(main())

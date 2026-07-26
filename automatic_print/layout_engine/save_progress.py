from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from threading import Event, Thread


@contextmanager
def monitor_save(path: Path, progress):
    if progress is None:
        yield
        return
    stopped = Event()

    def report_size() -> None:
        while not stopped.wait(0.5):
            try:
                size = path.stat().st_size if path.is_file() else 0
                progress("保存图片", size, 0, path.name)
            except Exception:
                return

    progress("保存图片", 0, 0, path.name)
    reporter = Thread(target=report_size, daemon=True)
    reporter.start()
    try:
        yield
    finally:
        stopped.set()
        reporter.join(timeout=1)

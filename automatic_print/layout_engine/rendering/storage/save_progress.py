from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Lock, Thread
from time import perf_counter


@dataclass
class SaveObservation:
    started: float = field(default_factory=perf_counter)
    first_write: float | None = None
    last_growth: float | None = None
    finished: float | None = None
    bytes_written: int = 0
    lock: Lock = field(default_factory=Lock)

    def sample(self, path: Path) -> None:
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        now = perf_counter()
        with self.lock:
            if size > 0 and self.first_write is None:
                self.first_write = now
            if size != self.bytes_written:
                self.last_growth = now
                self.bytes_written = size

    def close(self, path: Path) -> None:
        self.sample(path)
        self.finished = perf_counter()

    def steps(self) -> list[dict]:
        end = self.finished or perf_counter()
        first = self.first_write or end
        last = self.last_growth or first
        return [
            {"name": "启动至首批PNG数据（含首段延迟合成）",
             "seconds": max(0.0, first - self.started)},
            {"name": "PNG持续生成、压缩与写入",
             "seconds": max(0.0, last - first)},
            {"name": "编码收尾与文件刷新",
             "seconds": max(0.0, end - last)},
        ]


@contextmanager
def monitor_save(path: Path, progress):
    observation = SaveObservation()
    stopped = Event()

    def report_size() -> None:
        while not stopped.wait(0.1):
            try:
                observation.sample(path)
                if progress:
                    progress(
                        "保存图片", observation.bytes_written, 0, path.name
                    )
            except Exception:
                return

    if progress:
        progress("保存图片", 0, 0, path.name)
    reporter = Thread(target=report_size, name='save-progress', daemon=True)
    reporter.start()
    try:
        yield observation
    finally:
        stopped.set()
        reporter.join()  # Never return with a reporter still using worker callbacks.
        observation.close(path)

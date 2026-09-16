"""Own the single-batch worker thread and its signal routing."""
from PySide6.QtCore import QThread, Qt

from .thread_lifecycle import (
    defer_finished_thread_cleanup,
    discard_stopped_thread,
)


class LayoutGenerationController:
    """Keep task lifecycle out of the main window's presentation code."""

    def __init__(self, owner) -> None:
        self.owner = owner

    @property
    def active(self) -> bool:
        return self.owner.thread is not None

    def prepare(self) -> bool:
        if self.owner.thread is None:
            return True
        return discard_stopped_thread(self.owner, 'thread', 'worker')

    def start(self, worker, bridge) -> None:
        thread = QThread(self.owner)
        self.owner.thread = thread
        self.owner.worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        queued = Qt.ConnectionType.QueuedConnection
        for signal, target in (
            (worker.sources_ready, bridge.layout_sources),
            (worker.progress, bridge.layout_progress),
            (worker.timings_ready, bridge.layout_timings),
            (worker.preview_ready, bridge.layout_preview),
            (worker.analysis_ready, bridge.layout_analysis),
            (worker.finished, bridge.layout_finished),
            (worker.failed, bridge.layout_failed),
            (worker.cancelled, bridge.layout_cancelled),
        ):
            signal.connect(target, queued)
        for terminal in (worker.finished, worker.failed, worker.cancelled):
            terminal.connect(thread.quit)
            terminal.connect(worker.deleteLater)
        thread.finished.connect(self.clear)
        thread.start()

    def request_cancel(self) -> bool:
        worker = self.owner.worker
        if self.owner.thread is None or worker is None:
            return False
        worker.request_cancel()
        return True

    def clear(self) -> None:
        defer_finished_thread_cleanup(self.owner, 'thread', 'worker')

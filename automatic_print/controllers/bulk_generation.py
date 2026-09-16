"""Thread lifecycle for the rolling multi-batch worker."""
from PySide6.QtCore import QThread, Qt


class BulkGenerationController:
    def __init__(self, owner) -> None:
        self.owner = owner

    def start(self, worker, bindings, cleanup) -> None:
        thread = QThread(self.owner)
        self.owner.thread = thread
        self.owner.worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        for signal, slot in bindings:
            signal.connect(slot, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(cleanup)
        thread.start()

    def request_cancel(self) -> bool:
        worker = self.owner.worker
        if self.owner.thread is None or worker is None:
            return False
        worker.cancellation.request()
        return True

    def clear(self) -> None:
        thread = self.owner.thread
        if thread is not None:
            thread.deleteLater()
        self.owner.thread = self.owner.worker = None

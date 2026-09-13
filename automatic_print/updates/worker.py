from PySide6.QtCore import QObject, Signal, Slot
from .source import SourceUpdater, PROJECT_ROOT


class SourceUpdateWorker(QObject):
    progress = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, info=None, root=PROJECT_ROOT):
        super().__init__()
        self.info, self.root = info, root

    @Slot()
    def run(self):
        try:
            updater = SourceUpdater(self.root, self.progress.emit)
            result = updater.apply(self.info) if self.info else updater.check()
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))

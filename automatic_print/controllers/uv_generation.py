"""Thread lifecycle for one UV fixed-sheet generation task."""

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot


class UvGenerationWorker(QObject):
    progress = Signal(str, int, int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, folder, material_key):
        super().__init__()
        self.folder = Path(folder)
        self.material_key = material_key

    @Slot()
    def run(self):
        try:
            from ..layout_engine.uv import generate_uv_sheet
            result = generate_uv_sheet(
                self.folder, self.progress.emit, spec=self.material_key
            )
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.finished.emit(result)


class UvGenerationController(QObject):
    progress = Signal(str, int, int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.thread = None
        self.worker = None

    @property
    def active(self):
        return self.thread is not None

    def start(self, folder, material_key="2030_iron"):
        if self.active:
            return False
        self.thread = QThread(self)
        self.worker = UvGenerationWorker(folder, material_key)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.progress)
        self.worker.finished.connect(self.finished)
        self.worker.failed.connect(self.failed)
        for terminal in (self.worker.finished, self.worker.failed):
            terminal.connect(self.worker.deleteLater)
            terminal.connect(self.thread.quit)
        self.thread.finished.connect(self._clear)
        self.thread.start()
        return True

    @Slot()
    def _clear(self):
        thread = self.thread
        self.thread = None
        self.worker = None
        if thread is not None:
            thread.deleteLater()

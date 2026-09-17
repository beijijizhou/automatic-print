"""Read visible QR bounds one at a time without blocking GUI painting."""
from collections import OrderedDict, deque

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot

from ..layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band


class ResultSignal(QObject):
    ready = Signal(object, object)


class BandTask(QRunnable):
    def __init__(self, key):
        super().__init__()
        self.key = key
        self.signals = ResultSignal()

    def run(self):
        try:
            band = detect_guide_band(self.key[0])
        except Exception:
            band = None
        try:
            self.signals.ready.emit(self.key, band)
        except RuntimeError:
            # Window/app shutdown may destroy the signal object during QR detection.
            # A late thumbnail result is disposable; never touch closed GUI objects.
            pass


class CutGuideCache(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = OrderedDict()
        self.pending = deque()
        self.active = None
        self.generation = 0

    def clear(self):
        self.generation += 1
        self.values.clear()
        self.pending.clear()

    def request(self, paths):
        bands, missing, waiting, wanted = {}, [], [], set()
        for path in paths:
            try:
                stat = path.stat()
                key = (path, stat.st_mtime_ns, stat.st_size, self.generation)
            except OSError:
                missing.append(path)
                continue
            wanted.add(key)
            if key in self.values:
                band = self.values[key]
                if band is None:
                    missing.append(path)
                else:
                    bands[path] = band
            else:
                waiting.append(path)
                if key not in self.pending and (self.active is None or self.active.key != key):
                    self.pending.append(key)
        self.pending = deque(key for key in self.pending if key in wanted)
        self._start()
        return bands, missing, waiting

    def _start(self):
        if self.active is not None or not self.pending:
            return
        self.active = BandTask(self.pending.popleft())
        self.active.signals.ready.connect(self._ready, Qt.QueuedConnection)
        QThreadPool.globalInstance().start(self.active)

    @Slot(object, object)
    def _ready(self, key, band):
        if key[-1] == self.generation:
            self.values[key] = band
            while len(self.values) > 512:
                self.values.popitem(last=False)
        self.active = None
        self._start()
        self.changed.emit()

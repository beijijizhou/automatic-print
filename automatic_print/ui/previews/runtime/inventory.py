"""Fast filename-only batch inventory used before layout starts."""
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot

from ....runtime.cancellation import Cancellation, TaskCancelled
from ....layout_engine import discover_images
from ....layout_engine.orders.batch_analysis import batch_inventory


class InventorySignals(QObject):
    report = Signal(object, object)
    finished = Signal(object)


class InventoryTask(QRunnable):
    def __init__(self, token, folder, settings):
        super().__init__()
        self.token, self.folder, self.settings = token, folder, settings
        self.cancel = Cancellation()
        self.signals = InventorySignals()

    def run(self):
        try:
            paths = discover_images(self.folder) if self.folder and self.folder.is_dir() else []
            self.cancel.check()
            if not paths:
                return
            report = batch_inventory(paths)
            from ....automation.api.s2b.metadata.batch_name import find_s2b_batch_folder
            if any(find_s2b_batch_folder(path) for path in paths):
                report['s2b_metadata_pending'] = True
            self.signals.report.emit(self.token, deepcopy(report))
            from ....automation.api.s2b.metadata.prepare import prepare_s2b_metadata
            metadata = prepare_s2b_metadata(paths, self.settings)
            self.cancel.check()
            if metadata:
                report = batch_inventory(paths)
            report.pop('s2b_metadata_pending', None)
            if metadata:
                report['s2b_metadata'] = metadata
            self.signals.report.emit(self.token, report)
        except (TaskCancelled, OSError, ValueError):
            pass
        finally:
            self.signals.finished.emit(self.token)


class InventoryLoader(QObject):
    def __init__(self, preview):
        super().__init__(preview)
        self.preview = preview
        self.token, self.active, self.closed = 0, None, False

    def invalidate(self):
        self.token += 1
        if self.active:
            self.active.cancel.request()

    def request(self, folder, settings):
        self.invalidate()
        if self.closed:
            return
        self.active = InventoryTask(self.token, folder, settings)
        self.active.signals.report.connect(self.report, Qt.QueuedConnection)
        self.active.signals.finished.connect(self.finished, Qt.QueuedConnection)
        QThreadPool.globalInstance().start(self.active)

    def stage(self, folder):
        preview = self.preview
        preview.source_folder, preview.path = None, None
        preview.clear_for_generation()
        path = Path(folder) if str(folder).strip() else None
        if path:
            try:
                self.request(path, preview.settings_getter())
            except ValueError:
                pass
        preview.detail = '正在读取批次名称、尺码与颜色；不会启动排版。'
        preview.production_stage = preview.detail
        preview.loading_status.emit(preview.detail)

    @Slot(object, object)
    def report(self, token, report):
        if token == self.token and not self.closed:
            self.preview.analysis_report = report
            self.preview.analysis_ready.emit(report)

    @Slot(object)
    def finished(self, token):
        if self.active and token == self.active.token:
            self.active = None
        if token == self.token and not self.closed:
            text = '批次名称、尺码与颜色已读取；点击开始排版。'
            self.preview.production_stage = text
            self.preview.loading_status.emit(text)

    def shutdown(self):
        self.closed = True
        self.invalidate()

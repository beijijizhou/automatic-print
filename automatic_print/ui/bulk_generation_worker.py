"""Reuse the complete production pipeline for each independently queued batch."""
from dataclasses import replace
from datetime import datetime
from time import monotonic
from uuid import uuid4
from PySide6.QtCore import QObject, Signal, Slot, Qt
from ..cancellation import Cancellation, TaskCancelled
from ..history.batch_queue import run_queue
from ..layout_engine.output_name import batch_output_directory
from .workers import GenerateWorker


class BulkGenerationWorker(QObject):
    progress = Signal(int, str, str, object, object, str)
    preview = Signal(int, object)
    finished = Signal(object)

    def __init__(self, folders, settings, parallelism, custom_base=None):
        super().__init__()
        self.folders, self.custom_base = folders, custom_base
        self.parallelism = max(1, min(parallelism, len(folders)))
        self.settings = replace(settings, worker_threads=max(1, settings.worker_threads//self.parallelism),
                                save_parallelism=1, film_geometry_workers=max(1, 4//self.parallelism))
        self.cancellation = Cancellation()

    def calculate(self, index, folder):
        self.cancellation.check()
        job = datetime.now().strftime('JOB_%Y%m%d_%H%M%S')+'_'+uuid4().hex[:8]
        output = batch_output_directory(self.custom_base or folder.parent, folder.name, job)
        worker = GenerateWorker(None, folder, output, job, self.settings)
        worker.cancellation = self.cancellation
        results, errors, stopped = [], [], []
        direct = Qt.DirectConnection
        def progress(stage, current, total, filename):
            self.progress.emit(index, str(folder), stage, current, total, filename)
        worker.progress.connect(progress, direct)
        worker.preview_ready.connect(lambda payload: self.preview.emit(index, payload), direct)
        worker.finished.connect(lambda path, result: results.append(dict(output=path, result=result)), direct)
        worker.failed.connect(errors.append, direct)
        worker.cancelled.connect(lambda: stopped.append(True), direct)
        worker.run()  # QObject is constructed, used and released in this same pool thread.
        if errors:
            raise ValueError(errors[0])
        if stopped:
            raise TaskCancelled()
        if not results:
            raise RuntimeError('批次未返回生成结果')
        self.progress.emit(index, str(folder), '批次生成完成', 1, 1, str(output))
        return dict(results[0], folder=str(folder))

    @Slot()
    def run(self):
        started = monotonic()
        def failed(index, folder, error):
            self.progress.emit(index, str(folder), '批次失败，继续下一批', 0, 0, error)
        try:
            result = run_queue(self.folders, self.calculate, self.parallelism, self.cancellation, failed)
        except Exception as error:
            result = {'records': [], 'errors': [{'folder': '', 'error': str(error)}], 'stopped': False}
        self.finished.emit(dict(result, seconds=monotonic()-started))

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
    discovered = Signal(object)
    progress = Signal(int, str, str, object, object, str)
    preview = Signal(int, object)
    finished = Signal(object)
    completed = Signal(int, object)
    timings = Signal(int, object)

    def __init__(self, folders, settings, parallelism, custom_base=None, preview_only=False, source_root=None):
        super().__init__()
        self.folders, self.custom_base = folders, custom_base
        self.preview_only = preview_only
        self.source_root, self.inventory = source_root, {}
        self.original_settings = settings
        self.parallelism = max(1, min(parallelism, len(folders))) if folders else max(1, parallelism)
        self.settings = replace(settings, worker_threads=max(1, settings.worker_threads//self.parallelism),
                                save_parallelism=1, film_geometry_workers=max(1, 4//self.parallelism))
        self.cancellation = Cancellation()

    def calculate(self, index, folder):
        self.cancellation.check()
        job = datetime.now().strftime('JOB_%Y%m%d_%H%M%S')+'_'+uuid4().hex[:8]
        base, parts = self.custom_base or folder.parent, ()
        if self.source_root is not None:
            base = self.custom_base or self.source_root.parent
            parts = ((self.source_root.name,) if self.source_root.name else ())+folder.relative_to(self.source_root).parts
        output = batch_output_directory(base, folder.name, job, parts)
        images = self.inventory[folder]['images'] if folder in self.inventory else None
        worker = GenerateWorker(images, folder, output, job, self.settings, preview_only=self.preview_only)
        worker.cancellation = self.cancellation
        results, errors, stopped = [], [], []
        direct = Qt.DirectConnection
        def progress(stage, current, total, filename):
            self.progress.emit(index, str(folder), stage, current, total, filename)
        worker.progress.connect(progress, direct)
        worker.preview_ready.connect(lambda payload: self.preview.emit(index, payload), direct)
        worker.timings_ready.connect(lambda data: self.timings.emit(index, data), direct)
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
        record = dict(results[0], folder=str(folder))
        self.completed.emit(index, record)
        self.progress.emit(index, str(folder), '批次预览完成' if self.preview_only else '批次生成完成', 1, 1,
                           '未生成文件' if self.preview_only else str(output))
        return record

    @Slot()
    def run(self):
        started = monotonic()
        def failed(index, folder, error):
            self.progress.emit(index, str(folder), '批次失败，继续下一批', 0, 0, error)
        try:
            scan_errors = []
            if self.source_root is not None:
                from ..layout_engine.batch_discovery import scan_batches
                scan = scan_batches(self.source_root, lambda *a: self.progress.emit(-1, str(self.source_root), *a),
                                    self.cancellation)
                self.inventory = {b['folder']: b for b in scan['batches']}
                self.folders = list(self.inventory)
                self.parallelism = max(1, min(self.parallelism, len(self.folders)))
                config = self.original_settings
                self.settings = replace(config, worker_threads=max(1, config.worker_threads//self.parallelism),
                                        save_parallelism=1, film_geometry_workers=max(1, 4//self.parallelism))
                scan_errors = scan['errors']
                self.discovered.emit(scan)
            result = run_queue(self.folders, self.calculate, self.parallelism, self.cancellation, failed)
            result['errors'] = scan_errors+result['errors']
        except TaskCancelled:
            result = {'records': [], 'errors': [], 'stopped': True}
        except Exception as error:
            result = {'records': [], 'errors': [{'folder': '', 'error': str(error)}], 'stopped': False}
        self.finished.emit(dict(result, seconds=monotonic()-started))

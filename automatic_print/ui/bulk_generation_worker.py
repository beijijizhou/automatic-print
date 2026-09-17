"""Reuse the complete production pipeline for each independently queued batch."""
from dataclasses import replace
from datetime import datetime
from time import monotonic
from uuid import uuid4
from PySide6.QtCore import QObject, Signal, Slot, Qt
from ..runtime.cancellation import Cancellation, TaskCancelled
from ..history.batch_queue import run_queue
from ..layout_engine.output.output_name import batch_output_directory
from .workers import GenerateWorker


class BulkGenerationWorker(QObject):
    discovered = Signal(object)
    progress = Signal(int, str, str, object, object, str)
    preview = Signal(int, object)
    finished = Signal(object)
    completed = Signal(int, object)
    timings = Signal(int, object)
    source_progress = Signal(int, str, str, object, object, str)

    def __init__(self, folders, settings, parallelism, custom_base=None, preview_only=False,
                 source_root=None, combine_batches=False):
        super().__init__()
        self.folders, self.custom_base = folders, custom_base
        self.preview_only = preview_only
        self.source_root, self.inventory = source_root, {}
        self.combine_batches = combine_batches
        self.image_sources,self.source_totals,self.source_done={},{},{}
        # Output grouping follows the scanned source structure. Choosing a
        # platform in the UI must never change single/multi-batch semantics.
        self.group_outputs = False
        self.original_settings = settings
        self.parallelism = max(1, min(parallelism, len(folders))) if folders else max(1, parallelism)
        self.settings = replace(settings, worker_threads=max(1, settings.worker_threads//self.parallelism),
                                save_parallelism=1, film_geometry_workers=max(1, 4//self.parallelism))
        self.cancellation = Cancellation()

    def calculate(self, index, folder):
        self.cancellation.check()
        job = datetime.now().strftime('JOB_%Y%m%d_%H%M%S')+'_'+uuid4().hex[:8]
        base = self.custom_base or folder.parent
        if self.source_root is not None:
            base = self.custom_base or self.source_root.parent
            relative = folder.relative_to(self.source_root).parts
            grouped = self.group_outputs
            batch_name = ' - '.join(relative) if grouped and relative else folder.name
        else:
            batch_name = folder.name
        output = batch_output_directory(base, batch_name, job)
        images = self.inventory[folder]['images'] if folder in self.inventory else None
        worker = GenerateWorker(images, folder, output, job, self.settings,
                                preview_only=self.preview_only,batch_name=batch_name)
        worker.cancellation = self.cancellation
        results, errors, stopped = [], [], []
        direct = Qt.DirectConnection
        def progress(stage, current, total, filename):
            token,separator,detail=filename.partition('\t')
            display=stage
            if total and stage in {'读取图片尺寸','测量标签与刀码'}:
                from ..layout_engine.measurement.parallel_measurement import measurement_workers
                display=f'{stage} · {measurement_workers(self.settings.worker_threads,total)}线程并行'
            elif total and stage=='合成图片':
                display=f'{stage} · {min(self.settings.worker_threads,total)}路图片准备'
            source=self.image_sources.get(token) if separator else None
            if separator and stage=='测量标签与刀码' and current==1:
                self.source_done={key:value for key,value in self.source_done.items() if key[1]!=stage}
            if source and stage=='测量标签与刀码':
                key=source,stage
                self.source_done[key]=self.source_done.get(key,0)+1
                self.source_progress.emit(index,source,display,self.source_done[key],
                                          self.source_totals[source],detail)
            self.progress.emit(index, str(folder), display, current, total, detail if separator else filename)
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
                           '未生成文件' if self.preview_only else results[0]['output'])
        return record

    @Slot()
    def run(self):
        started = monotonic()
        def failed(index, folder, error):
            self.progress.emit(index, str(folder), '批次失败，继续下一批', 0, 0, error)
        try:
            scan_errors = []
            if self.source_root is not None:
                from ..layout_engine.intake.discovery.batch_discovery import scan_batches
                scan = scan_batches(self.source_root, lambda *a: self.progress.emit(-1, str(self.source_root), *a),
                                    self.cancellation)
                self.inventory = {b['folder']: b for b in scan['batches']}
                if scan.get('platform')=='S2B':
                    self.group_outputs=True
                    self.original_settings=replace(self.original_settings,platform_name='S2B')
                if self.combine_batches and scan['batches']:
                    sources=scan['batches']
                    for batch in sources:
                        source=str(batch['folder'])
                        self.source_totals[source]=batch['image_count']
                        self.image_sources.update((str(image),source) for image in batch['images'])
                    images=[image for batch in sources for image in batch['images']]
                    combined={'folder':self.source_root, 'relative':self.source_root.relative_to(self.source_root),
                              'images':images, 'image_count':len(images), 'source_batches':sources}
                    scan=dict(scan,batches=[combined],combined_batch_count=len(sources))
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

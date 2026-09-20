from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from ..runtime.cancellation import Cancellation, TaskCancelled
from ..layout_engine import LayoutSettings, generate_layout, discover_images, discovered_extensions
from ..updates.release import fetch_latest_release
from ..layout_engine.reporting.operation_timing import OperationTiming, PROGRESS_PHASES, timing_report
from ..layout_engine.output.output_sizes import cutting_report


class GenerateWorker(QObject):
    sources_ready = Signal(object)
    timings_ready = Signal(object)
    preview_ready = Signal(object)
    analysis_ready = Signal(object)
    progress = Signal(str, object, object, str)
    finished = Signal(str, object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        images: list[Path],
        source: Path,
        output: Path,
        job_id: str,
        settings: LayoutSettings,
        preview_only=False,
        batch_name=None,
        local_mirror_root=None,
    ) -> None:
        super().__init__()
        self.images = images
        self.source = source
        self.output = output
        self.job_id = job_id
        self.settings = settings
        self.preview_only = preview_only
        self.batch_name = batch_name or self.source.resolve().name
        self.local_mirror_root = local_mirror_root
        self.image_aliases = {}
        self.cancellation = Cancellation()
        self.timing = None
        self.failure_stage = '开始读取批次'

    def _phase(self, name):
        self.failure_stage = name
        self.cancellation.check()
        if self.timing.phase(name):
            self.timings_ready.emit(self.timing.snapshot())

    def request_cancel(self) -> None:
        self.cancellation.request()

    def _save_history(self, result):
        try:
            from ..history.store import save_run
            save_run(self.job_id, self.source, self.output, self.settings, result)
        except Exception as error:
            result['history_warning'] = f'本地排版历史保存失败：{error}'
            self.progress.emit('历史保存失败', 0, 0, result['history_warning'])

    def _progress(self, stage, current, total, filename) -> None:
        self.cancellation.check()
        if stage in PROGRESS_PHASES:
            self._phase(PROGRESS_PHASES[stage])
        token, separator, detail = filename.partition('\t')
        if separator and token in self.image_aliases:
            filename = self.image_aliases[token] + '\t' + detail
        self.progress.emit(stage, current, total, filename)

    def _prefer_local_mirror(self):
        from ..automation.transfer.local_mirror import prefer_downloaded_batch
        selected = prefer_downloaded_batch(
            self.images, self.source, self.local_mirror_root,
            self.settings.platform_name,
        )
        if not selected.used:
            return
        self.images = list(selected.images)
        self.image_aliases = selected.aliases
        self._progress('共享盘本地副本', len(self.images), len(self.images), selected.detail)

    @Slot()
    def run(self) -> None:
        self.timing = OperationTiming()
        try:
            if not self.preview_only:
                self.output.mkdir(parents=True, exist_ok=True)
                marker = self.output / '批次生成未完成.txt'
                marker.write_text('本批次尚未全部完成或被中途退出，任务状态和已有结果已保留，请由用户选择后续处理。\n'
                                  '已完成的其他批次不受影响；请重新生成此批次。', encoding='utf-8')
            self._phase('扫描文件名')
            self.cancellation.check()
            if self.images is None:
                self._progress('扫描文件夹', 0, 0, str(self.source))
                self.images = discover_images(self.source)
                if not self.images:
                    types = '、'.join(discovered_extensions(self.source)[:15]) or '没有文件'
                    raise ValueError(f'所选文件夹没有支持的图片。实际文件类型：{types}')
            self._prefer_local_mirror()
            self.sources_ready.emit(self.images)
            # Filename-only facts are available before DPI reads or image decoding.
            try:
                from ..layout_engine.orders.batch_analysis import batch_inventory
                self.analysis_ready.emit(batch_inventory(self.images))
            except Exception as error:
                self.progress.emit('文件名分组待核对', 0, 0, str(error))
            self.cancellation.check()
            result = generate_layout(
                self.images, self.output, self.settings, self._progress,
                plan_ready=self.preview_ready.emit, preview_only=self.preview_only,
                analysis_ready=self.analysis_ready.emit,
                batch_name=self.batch_name,
                phase_ready=self._phase,
                split_by_knife=(not self.preview_only and self.settings.cutter_mode == 'dual'),
            )
            self.cancellation.check()
            result['operation_timings'] = self.timing.finish()
            self.timings_ready.emit(result['operation_timings'])
            if self.preview_only:
                report_text = cutting_report(result)
                result['report_text'] = (
                    report_text + '\n\n耗时与并行处理\n' +
                    timing_report(result['operation_timings'])
                )
                self._save_history(result)
                self.finished.emit("", result)
                return
            from ..layout_engine.output.output_name import (
                finish_output_files, output_log_path, remap_result_files,
            )
            from ..layout_engine.cutting.knife_folders import knife_output_folders
            self._progress('整理输出文件夹',0,1,'将合格排版图移入切膜机文件')
            files = result.get('files') or [result['filename']]
            folders = knife_output_folders(result)
            marker.unlink(missing_ok=True)
            self.output, mapping = finish_output_files(self.output, files, folders)
            remap_result_files(result, mapping)
            self._progress('整理输出文件夹',1,1,str(self.output))
            report_text = timing_report(result['operation_timings'])
            if 'actual_save_parallelism' in result:
                report_text += (f"\n分段保存：{result['segment_count']} 个文件 · 同时处理 {result['actual_save_parallelism']} 段"
                                f" · {'不限制内存预算' if result['save_memory_unlimited'] else '使用内存预算'}")
            for part in result.get('parts', []):
                report_text += f"\n\n第{part['segment_index']:03d}段：{part['filename']}\n"
                report_text += timing_report(part['operation_timings']).replace(
                    '计时从文件名扫描开始，到批次信息整理完成',
                    '本段计时从复用整批排版开始，到本段信息整理完成')
            combined = cutting_report(result) + '\n\n耗时与并行处理\n' + report_text
            try:
                output_log_path(self.output, result['filename']).write_text(combined, encoding='utf-8')
            except OSError as error:
                result['log_warning'] = f'排版图已完成，但日志保存失败：{error}'
                self.progress.emit('日志保存失败', 0, 0, result['log_warning'])
            self._save_history(result)
        except TaskCancelled:
            self.timings_ready.emit(self.timing.finish('已停止'))
            self.cancelled.emit()
            return
        except Exception as error:
            self.timings_ready.emit(self.timing.finish('失败'))
            from ..layout_engine.diagnostics.error_context import error_context
            message = error_context(error, self.images, self.source, self.failure_stage, self.settings)
            try:
                if self.output.is_dir():
                    (self.output/'失败诊断.txt').write_text(message, encoding='utf-8')
            except OSError:
                pass  # Diagnostic writes must not hide the actual production error.
            self.failed.emit(message)
            return
        self.finished.emit(str(self.output), result)


class UpdateWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(fetch_latest_release())
        except Exception as error:
            self.failed.emit(str(error))

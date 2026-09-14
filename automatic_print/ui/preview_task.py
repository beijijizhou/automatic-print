"""Pure-data background preview; never create widgets or text documents here."""
from dataclasses import replace

from PySide6.QtCore import QObject, QRunnable, Signal

from ..cancellation import Cancellation, TaskCancelled
from ..layout import discover_images
from ..layout_engine.planner import plan_layout
from ..layout_engine.models import mm_to_px
from ..layout_engine.order_validation import validate_order_placements
from ..layout_engine.cut_validation import validate_cut_corridor
from .preview_diagnostics import diagnostic_layout


class PreviewSignals(QObject):
    progress = Signal(object, str)
    sources = Signal(object, object)
    analysis = Signal(object, object)
    finished = Signal(object, object, str)


class PreviewTask(QRunnable):
    def __init__(self, token, folder, settings):
        super().__init__()
        self.token, self.folder, self.settings = token, folder, settings
        self.signals = PreviewSignals()
        self.cancel = Cancellation()

    def emit(self, signal, *args):
        self.cancel.check()
        try:
            signal.emit(self.token, *args)
        except RuntimeError:
            raise TaskCancelled()

    def run(self):
        payload, error = None, ''
        try:
            self.emit(self.signals.progress, '正在扫描文件夹并读取图片文件名…')
            paths = discover_images(self.folder) if self.folder and self.folder.is_dir() else []
            self.emit(self.signals.sources, paths)
            if not paths:
                raise ValueError('所选文件夹没有可读取的图片，请重新选择。')
            from ..layout_engine.header_gap import prepare_paths
            paths, self.settings, gap_records = prepare_paths(paths, self.settings,
                lambda stage, current, total, name: self.emit(self.signals.progress,
                    f'{stage} · {current}/{total} · {name}'))
            from ..layout_engine.output_dpi import resolve_output_dpi
            self.settings = resolve_output_dpi(paths, self.settings,
                lambda stage, current, total, name: self.emit(self.signals.progress,
                    f'{stage} · {current}/{total} · {name}'))
            effective, reports = [self.settings], []

            def progress(stage, current, total, filename):
                if stage == '批次刀位已确定':
                    effective[0] = replace(self.settings, cutter_knife_mm=current*25.4/total)
                self.emit(self.signals.progress, f'{stage} · {current}/{total} · {filename}')

            def analysis(report):
                from ..layout_engine.header_gap import annotate_analysis
                annotate_analysis(report, gap_records)
                reports[:] = [report]
                self.emit(self.signals.analysis, report)

            warning, overflow, order_check = '', [], {}
            try:
                planned, labels, _, height, baseline = plan_layout(paths, self.settings, progress,
                                                                  analysis_ready=analysis)
                order_check = validate_order_placements(paths, planned)
                validate_cut_corridor(planned, effective[0],
                                     mm_to_px(self.settings.media_width_mm, self.settings.dpi))
            except ValueError as exc:
                warning = f'仅供检查，当前参数禁止输出：{exc}'
                self.emit(self.signals.progress, '参数不安全，正在准备仅供检查的图片预览…')
                planned, labels, height, overflow = diagnostic_layout(paths, effective[0], progress)
                baseline = height
            payload = {'planned': planned, 'labels': labels, 'settings': effective[0],
                       'warning': warning, 'overflow': overflow, 'order_check': order_check,
                       'analysis': reports[-1] if reports else {}, 'header_gap': gap_records,
                       'saved_meters': max(0, baseline-height)*25.4/self.settings.dpi/1000}
            self.cancel.check()
        except TaskCancelled:
            error = '预览任务已停止。'
        except Exception as exc:
            error = str(exc)
        try:
            self.signals.finished.emit(self.token, payload, error)
        except RuntimeError:
            pass  # Closed window: its disposable preview result is no longer needed.

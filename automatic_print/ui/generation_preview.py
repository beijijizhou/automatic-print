from PySide6.QtCore import QObject, Slot
from pathlib import Path

from .previews.runtime.snapshot import install_snapshot
from ..layout_engine.orders.order_groups import detail_members


class GenerationPreviewController(QObject):
    """GUI-thread-only presentation of immutable worker layout data."""
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.panel = window.automation_home.label_quick_panel
        self.preview = self.panel.preview
        self.payload = None
        bridge = window.worker_bridge
        bridge.layout_preview.connect(self.ready)
        bridge.layout_sources.connect(self.sources)
        bridge.layout_analysis.connect(self.panel.analysis.show_report)
        bridge.layout_analysis.connect(self.panel.summary.show_analysis)
        bridge.layout_finished.connect(self.panel.summary.finished)
        bridge.layout_progress.connect(self.progress)
        for signal in (bridge.layout_finished, bridge.layout_cancelled):
            signal.connect(self.end)
        bridge.layout_failed.connect(self.failed)
        bridge.layout_cancelled.connect(self.cancelled)

    def start(self, mode='single'):
        from .busy_spinner import show_busy
        show_busy(self.window)
        self.window.layout_activity.start(mode)
        self.panel.marker_examples.clear_batch()
        bulk = getattr(self.window, 'bulk_controller', None)
        if bulk:
            bulk.selector.hide()
        self.panel.timings.reset()
        self.payload = None
        self.panel.analysis.clear()
        folder = self.window.folder.text().strip()
        self.panel.summary.start(folder)
        self.panel.summary.progress.hide()
        self.panel.preview_scroll.verticalScrollBar().setValue(0)
        self.preview.clear_for_generation()
        self.preview.source_folder = Path(folder)
        self.preview.production_active = True
        self.preview.composed_count = 0
        self.window.automation_home.start_layout_button.setEnabled(False)
        self.window.automation_home.preview_only.setEnabled(False)
        self.panel.bulk_generation_button.setEnabled(False)
        self.preview.production_stage = "正在读取整批图片并计算固定刀位…"
        self.panel.manual_rotation.setEnabled(False)
        self.preview.update()
        self.window.settings_dialog.hide()
        self.window.automation_home.workbench_scroll.verticalScrollBar().setValue(0)

    @Slot(object)
    def sources(self, paths):
        self.panel.summary.start(self.window.folder.text(), len(paths))
        self.window.run_log.appendPlainText(f'已扫描 {len(paths)} 张图片，开始读取尺寸和排版。')
        self.preview.sources_ready.emit(paths)

    @Slot(object)
    def ready(self, payload):
        self.panel.marker_examples.use_batch(payload)
        self.panel.preview_tabs.setCurrentIndex(0)
        self.payload = payload
        self.preview.production_stage = '本批次排版已确定，正在处理输出…'
        self.panel.analysis.show_report(payload['analysis'])
        self.panel.summary.show_plan(payload)
        self.preview.batch_payload = payload
        quality = payload.get('dual_quality', {}).get('text')
        if quality:
            self.window.run_log.appendPlainText('排版方案：'+quality)
        if payload["settings"].cutter_mode == "dual":
            self.window.cutter_settings.knife.setValue(payload["settings"].cutter_knife_mm)
        self.preview.refresh_timer.stop()
        self.preview.sources_ready.emit(list(dict.fromkeys(path for path, _ in payload['planned'])))
        self.show_pair(0)

    def show_pair(self, index):
        if not self.payload:
            return
        planned = self.payload["planned"]
        if self.preview.overview and self.preview.planned and self.preview.render_settings is self.payload["settings"]:
            return
        start = min(max(0, index), max(0, len(planned)-2))
        settings = self.payload["settings"]
        try:
            install_snapshot(self.preview, planned if self.preview.overview else detail_members(planned, index=start), self.payload["labels"], settings, warning=self.payload.get("warning", ""))
            from .knife_caption import knife_caption
            knives = knife_caption(planned, settings.dpi)
            mode = ('整批轻量结构图（不读取缩略图）' if self.preview.overview
                    else '当前订单真实图片')
            self.preview.detail = f"{mode} · {knives or f'固定刀位 {settings.cutter_knife_mm:.1f} 毫米'} · 共 {len(planned)} 张 · 节省 {self.payload.get('saved_meters',0):.3f} 米"
        except (ValueError, OSError) as error:
            self.preview.warning = f"保留上次预览：{error}"
        self.preview.update()

    @Slot(str, object, object, str)
    def progress(self, stage, current, total, filename):
        if not self.preview.production_active:
            return
        filename=filename.split('\t',1)[-1]
        if stage == '膜规格比较' and current == 0:
            self.panel.summary.film_table.reset_rows('正在计算')
        self.preview.production_stage = filename if stage == "批次刀位已确定" else f"{stage} · {current}/{total}"
        self.panel.summary.progress.setText(f'{self.preview.production_stage} · {filename}')
        if stage == "合成图片":
            self.preview.composed_count = current
            self.show_pair(current-1)
        self.preview.update()

    def end(self, *_args):
        from .busy_spinner import show_progress
        show_progress(self.window)
        self.window.layout_activity.stop()
        self.panel.summary.progress.show()
        self.preview.production_active = False
        self.preview.composed_count = None
        self.window.automation_home.start_layout_button.setEnabled(True)
        self.window.automation_home.preview_only.setEnabled(True)
        self.panel.bulk_generation_button.setEnabled(True)
        self.preview.production_stage = "本次任务预览（保留实际刀位与排版位置）"
        self.panel.manual_rotation.setEnabled(True)
        self.preview.update()

    @Slot(str)
    def failed(self, message):
        self.panel.summary.show_failure(message)
        self.panel.analysis.failed(message)
        self.panel.summary.progress.setText('生成失败，禁止打印；完整原因见独立报错诊断区。')
        self.preview.warning = '生成失败，禁止打印；完整原因见独立报错诊断区。'
        self.end()

    @Slot()
    def cancelled(self):
        self.panel.summary.progress.setText('当前排版已停止；已计算的本批次信息保留，未完成结果不可打印。')

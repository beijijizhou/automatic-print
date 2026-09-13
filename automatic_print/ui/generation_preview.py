from PySide6.QtCore import QObject, Slot
from pathlib import Path

from .preview_snapshot import install_snapshot
from ..layout import discover_images
from ..layout_engine.order_groups import detail_members


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
        bridge.layout_analysis.connect(self.panel.analysis.show_report)
        bridge.layout_analysis.connect(self.panel.summary.show_analysis)
        bridge.layout_finished.connect(self.panel.summary.finished)
        bridge.layout_progress.connect(self.progress)
        for signal in (bridge.layout_finished, bridge.layout_cancelled):
            signal.connect(self.end)
        bridge.layout_failed.connect(self.failed)
        bridge.layout_cancelled.connect(self.cancelled)

    def start(self):
        self.payload = None
        self.panel.analysis.clear()
        folder = self.window.folder.text().strip()
        self.panel.summary.start(folder, len(discover_images(Path(folder))))
        self.panel.preview_scroll.verticalScrollBar().setValue(0)
        self.preview.clear_for_generation()
        self.preview.source_folder = Path(folder)
        self.preview.production_active = True
        self.preview.production_stage = "正在读取整批图片并计算固定刀位…"
        self.panel.manual_rotation.setEnabled(False)
        self.preview.update()
        self.window.settings_dialog.hide()
        self.window.automation_home.workbench_scroll.verticalScrollBar().setValue(0)

    @Slot(object)
    def ready(self, payload):
        self.payload = payload
        self.preview.production_stage = '本批次排版已确定，正在处理输出…'
        self.panel.analysis.show_report(payload['analysis'])
        self.panel.summary.show_plan(payload)
        self.preview.batch_payload = payload
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
            zones = dict((p.cut_zone,p.cut_knife_x_px) for _,p in planned if p.cut_zone)
            knives = " · ".join(f"{name}刀位 {knife*25.4/settings.dpi:.1f} 毫米" for name,knife in zones.items())
            self.preview.detail = f"{knives or f'固定刀位 {settings.cutter_knife_mm:.1f} 毫米'} · 共 {len(planned)} 张 · 节省 {self.payload.get('saved_meters',0):.3f} 米"
        except (ValueError, OSError) as error:
            self.preview.warning = f"保留上次预览：{error}"
        self.preview.update()

    @Slot(str, int, object, str)
    def progress(self, stage, current, total, filename):
        if not self.preview.production_active:
            return
        self.preview.production_stage = filename if stage == "批次刀位已确定" else f"{stage} · {current}/{total}"
        self.panel.summary.progress.setText(f'{self.preview.production_stage} · {filename}')
        if stage == "合成图片":
            self.show_pair(current-1)
        self.preview.update()

    def end(self, *_args):
        self.preview.production_active = False
        self.preview.production_stage = "本次任务预览（保留实际刀位与排版位置）"
        self.panel.manual_rotation.setEnabled(True)
        self.preview.update()

    @Slot(str)
    def failed(self, message):
        self.panel.analysis.failed(message)
        self.panel.summary.progress.setText(f'生成失败，禁止打印：{message}')
        self.preview.warning = f"生成失败，禁止打印：{message}"
        self.end()

    @Slot()
    def cancelled(self):
        self.panel.summary.progress.setText('当前排版已停止；已计算的本批次信息保留，未完成结果不可打印。')

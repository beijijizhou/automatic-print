"""Two-source preview of the real planner; no full-resolution output allocation."""
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPen, QPainter

from .production_preview import ProductionPreview
from .previews.runtime.loader import PreviewLoader
from .cut_guide_cache import CutGuideCache
from .cut_guide_preview import draw_cut_guides
from ..layout_engine.order_groups import detail_members
from .previews.runtime.snapshot import install_snapshot
from .layout_schematic import draw_preview_placement
from .previews.runtime.viewport import resize_preview


class PairProductionPreview(ProductionPreview):
    analysis_ready = Signal(object)
    analysis_failed = Signal(str)
    analysis_started = Signal()
    loading_status = Signal(str)
    sources_ready = Signal(object)
    plan_loaded = Signal(object)
    def __init__(self, settings_getter, parent=None):
        self.planned, self.images, self.badges = [], {}, {}
        self.platform_badges = {}
        self.canvas_width, self.canvas_height = 1, 1
        self.render_settings, self.warning, self.overflow = None, "", []
        self.production_active, self.production_stage = False, ""
        self.auto_refresh_enabled = True
        self.composed_count = None
        self.source_folder = None
        self.overview, self.batch_payload, self.batch_labels = False, None, {}
        self.analysis_report, self._schematic_report, self._schematic_items = {}, None, {}
        super().__init__(settings_getter, parent)
        self.cut_guides = CutGuideCache(self)
        self.cut_guides.changed.connect(self.update)
        self.guide_status = ""
        self.loader = PreviewLoader(self)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(120)
        self.refresh_timer.timeout.connect(self.refresh)
        self.setMinimumHeight(440)

    def use_folder(self, folder):
        self.cut_guides.clear()
        self.analysis_started.emit()
        self.source_folder = Path(folder) if str(folder).strip() else None
        self.path = None
        self.clear_for_generation()
        self.production_stage = '界面已就绪，等待后台读取图片文件夹…'
        self.loading_status.emit(self.production_stage)
        self.refresh_timer.start()

    def set_sample(self, path):
        self.path = Path(path) if path else None
        if self.batch_payload and self.path is not None:
            self.set_overview(self.overview)
        elif not self.production_active:
            self.invalidate_parameters()

    def schedule_refresh(self, *_args):
        if not self.auto_refresh_enabled or getattr(self, 'parameter_refresh_deferred', 0):
            return
        if self.source_folder is None and self.path is None:
            return
        self.refresh_timer.start()

    def invalidate_parameters(self, *_args):
        """Parameter edits never start analysis; only production buttons do."""
        self.refresh_timer.stop()
        self.loader.invalidate()
        self.cut_guides.clear()
        self.batch_payload, self.batch_labels = None, {}
        self.analysis_report = {}
        self._schematic_report, self._schematic_items = None, {}
        self.planned, self.images, self.badges = [], {}, {}
        self.item, self.render_settings = None, None
        self.warning, self.overflow = "", []
        message = "参数已修改；点击开始排版后重新计算。"
        self.detail = message
        self.production_stage = message
        self.loading_status.emit(message)
        self.update()

    def stage_folder(self, folder):
        self.source_folder, self.path = None, None
        self.clear_for_generation()
        self.detail = '已选择图片文件夹；点击开始排版，将统一读取、排版和保存。'
        self.production_stage = self.detail
        self.loading_status.emit(self.detail)

    def stop_loading(self):
        self.refresh_timer.stop()
        self.loader.stop()

    def clear_for_generation(self):
        self.loader.invalidate()
        self.cut_guides.clear()
        self.guide_status = ""
        self.refresh_timer.stop()
        self.batch_payload, self.batch_labels = None, {}
        self.analysis_report, self._schematic_report, self._schematic_items = {}, None, {}
        self.planned, self.images, self.badges = [], {}, {}
        self.item, self.render_settings = None, None
        self.warning, self.overflow = "", []
        self.detail = "正在生成新的批次排版，等待新预览…"
        self.setMinimumHeight(440)
        self.update()

    def set_overview(self, enabled):
        self.overview = enabled
        if self.batch_payload:
            data = self.batch_payload
            shown = data["planned"] if enabled else detail_members(data["planned"], self.path)
            install_snapshot(self, shown, data["labels"], data["settings"], data.get("warning", ""))
            self.update()
        else:
            self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        resize_preview(self)

    def refresh(self, *_args):
        if self.production_active:
            return
        folder = self.source_folder or (self.path.parent if self.path else None)
        if folder is None:
            self.planned, self.item, self.badges = [], None, {}
            self.warning, self.overflow = "", []
            self.detail = "选择图片文件夹后，自动显示两张图片的实际排版预览。"
            self.update()
            return
        self.refresh_timer.stop()
        try:
            settings = replace(self.settings_getter(), allow_rotation=False)
        except ValueError as error:
            self.warning = str(error)
            self.loading_status.emit(f'参数不安全，禁止输出：{error}')
            self.update()
            return
        self.loader.request(folder, settings)

    def closeEvent(self, event):
        self.refresh_timer.stop()
        self.loader.shutdown()
        super().closeEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), QColor("#f8fafc"))
            painter.setClipRect(_event.rect())
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            if self.item is not None:
                area = _event.rect()
                for y in range(max(0, area.top()//12*12), area.bottom()+1, 12):
                    for x in range(0, self.width(), 12):
                        painter.fillRect(QRectF(x, y, 12, 12), QColor("#e2e8f0" if (x//12+y//12)%2 else "#ffffff"))
                self._draw_sample(painter)
            painter.fillRect(QRectF(0, 0, self.width(), 78), QColor("#fff1f2" if self.warning else "#f8fafc"))
            painter.setPen(QColor("#b91c1c" if self.warning else "#475569"))
            painter.drawText(QRectF(12, 6, self.width()-24, 68), Qt.TextWordWrap,
                             self.warning or (self.production_stage + "\n" + self.detail + "\n" + self.guide_status).strip())
        finally:
            painter.end()

    def _draw_sample(self, painter):
        scale = min((self.width()-32)/self.canvas_width,
                    (self.height()-100)/self.canvas_height)
        if self.overview:
            scale = (self.width()-32)/self.canvas_width
        if hasattr(self, 'view_controls'):
            scale = self.view_controls.scale()
        painter.save()
        try:
            painter.translate((self.width()-self.canvas_width*scale)/2, 86)
            painter.scale(scale, scale)
            painter.setPen(QPen(QColor("#64748b"), 0))
            painter.drawRect(QRectF(0, 0, self.film_width, self.canvas_height))
            count = self.composed_count
            composed = {item.sequence_number for _, item in
                        (self.batch_payload or {}).get('planned', [])[:count]} if count is not None else set()
            for path, p in self.planned:
                rect = QRectF(p.x_px, p.y_px, p.width_px, p.height_px)
                if self.overview and not painter.clipBoundingRect().intersects(QRectF(0,p.row_y_px,self.canvas_width,p.footprint_height_px)):
                    continue
                pending = count is not None and p.sequence_number not in composed
                draw_preview_placement(self, painter, path, p, rect, pending, scale)
            draw_cut_guides(self, painter, scale)
            painter.setPen(QPen(QColor("#dc2626"), 0))
            for box in self.overflow:
                painter.fillRect(QRectF(*box), QColor(239, 68, 68, 90))
                painter.drawRect(QRectF(*box))
        finally:
            painter.restore()

"""Two-source preview of the real planner; no full-resolution output allocation."""
from dataclasses import replace
from pathlib import Path

from PIL.ImageQt import ImageQt
from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QImageReader, QPen, QTransform, QPainter

from .production_preview import ProductionPreview
from .cut_guide_cache import CutGuideCache
from .cut_guide_preview import draw_cut_guides
from ..layout_engine.order_groups import detail_members
from ..layout_engine.order_validation import validate_order_placements
from ..layout import discover_images
from ..layout_engine.dynamic_label import source_label_badge
from ..layout_engine.models import mm_to_px
from ..layout_engine.planner import plan_layout
from .preview_diagnostics import diagnostic_layout
from .preview_snapshot import install_snapshot
from .overview_assets import visible_assets
from ..layout_engine.cut_validation import validate_cut_corridor


class PairProductionPreview(ProductionPreview):
    analysis_ready = Signal(object)
    analysis_failed = Signal(str)
    analysis_started = Signal()
    def __init__(self, settings_getter, parent=None):
        self.planned, self.images, self.badges = [], {}, {}
        self.canvas_width, self.canvas_height = 1, 1
        self.render_settings, self.warning, self.overflow = None, "", []
        self.production_active, self.production_stage = False, ""
        self.source_folder = None
        self.overview, self.batch_payload, self.batch_labels = False, None, {}
        super().__init__(settings_getter, parent)
        self.cut_guides = CutGuideCache(self)
        self.cut_guides.changed.connect(self.update)
        self.guide_status = ""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(120)
        self.refresh_timer.timeout.connect(self.refresh)
        self.setMinimumHeight(440)

    def use_folder(self, folder):
        self.cut_guides.clear()
        self.analysis_started.emit()
        self.source_folder = Path(folder) if str(folder).strip() else None
        super().use_folder(folder)

    def schedule_refresh(self, *_args):
        self.refresh_timer.start()

    def clear_for_generation(self):
        self.cut_guides.clear()
        self.guide_status = ""
        self.refresh_timer.stop()
        self.batch_payload, self.batch_labels = None, {}
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
            self.refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.overview and self.item is not None:
            height = max(440, round(self.canvas_height*(self.width()-32)/self.canvas_width)+110)
            if self.minimumHeight() != height:
                self.setMinimumHeight(height)

    def refresh(self, *_args):
        if self.production_active:
            return
        if self.path is None:
            self.planned, self.item, self.badges = [], None, {}
            self.warning, self.overflow = "", []
            self.detail = "选择图片文件夹后，自动显示两张图片的实际排版预览。"
            self.update()
            return
        try:
            self.batch_payload = None
            paths = discover_images(self.source_folder or self.path.parent)
            index = paths.index(self.path) if self.path in paths else 0
            pair = paths[index:index+2]
            if len(pair) == 1 and len(paths) > 1:
                pair = paths[index-1:index+1]
            settings = replace(self.settings_getter(), allow_rotation=False)
            warning, overflow = "", []
            try:
                effective = [settings]
                def report(stage, current, total, filename):
                    if stage == "批次刀位已确定":
                        effective[0] = replace(settings, cutter_knife_mm=current*25.4/total)
                batch = paths
                planned, labels, _, height, baseline = plan_layout(batch, settings, report, analysis_ready=self.analysis_ready.emit)
                settings = effective[0]
                order_check = validate_order_placements(paths, planned)
                validate_cut_corridor(planned, settings, mm_to_px(settings.media_width_mm, settings.dpi))
                self.batch_payload = {"planned": planned, "labels": labels, "settings": settings, "order_check": order_check}
                if not self.overview:
                    planned = detail_members(planned, self.path)
            except ValueError as error:
                self.analysis_failed.emit(str(error))
                warning = f"仅供检查，当前参数禁止输出：{error}"
                planned, labels, height, overflow = diagnostic_layout(paths if self.overview else pair, settings)
            install_snapshot(self, planned, labels, settings, warning, overflow)
            parallel = len(planned) == 2 and planned[0][1].y_px == planned[1][1].y_px
            arrangement = "左右并排" if parallel else "上下排列（当前规则未允许或无法安全并排）"
            check_text = "禁止输出" if warning else ("整批贯穿检查通过" if settings.cutter_mode == "dual" else "当前模式不使用固定纵向刀位")
            if any(p.cut_zone for _,p in planned):
                check_text = "分区贯穿检查通过 · 进入旋转区换刀一次" if not warning else check_text
            knives = dict((p.cut_zone, p.cut_knife_x_px) for _, p in planned if p.cut_zone)
            knife_text = " / ".join(f"{name} {knife*25.4/settings.dpi:.1f} 毫米" for name, knife in knives.items())
            self.detail = f"{'整批总览' if self.overview else arrangement} · {len(planned)} 张图 · {knife_text or f'刀位 {settings.cutter_knife_mm:.1f} 毫米'} · {check_text}"
        except (OSError, ValueError) as error:
            self.analysis_failed.emit(str(error))
            self.warning = f"新预览未生成，保留上次预览（旧参数）：{error}"
        self.update()

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
        painter.save()
        try:
            painter.translate((self.width()-self.canvas_width*scale)/2, 86)
            painter.scale(scale, scale)
            painter.setPen(QPen(QColor("#64748b"), 0))
            painter.drawRect(QRectF(0, 0, self.film_width, self.canvas_height))
            settings = self.render_settings
            for path, p in self.planned:
                rect = QRectF(p.x_px, p.y_px, p.width_px, p.height_px)
                if self.overview and not painter.clipBoundingRect().intersects(QRectF(0,p.row_y_px,self.canvas_width,p.footprint_height_px)):
                    continue
                source = visible_assets(self, path, p) if self.overview else self.images[path]
                image = source.transformed(QTransform().rotate(-p.rotation_degrees))
                painter.drawImage(rect, image)
                painter.setPen(QPen(QColor("#94a3b8"), 0))
                painter.drawRect(rect)
                if path in self.badges:
                    painter.drawImage(QRectF(p.number_x_px, p.number_y_px,
                                            p.number_width_px, p.number_height_px), self.badges[path])
                if p.color_block_width_px:
                    painter.fillRect(QRectF(p.color_block_x_px, p.color_block_y_px,
                                           p.color_block_width_px, p.color_block_height_px),
                                     QColor(settings.color_block_color))
            draw_cut_guides(self, painter, scale)
            painter.setPen(QPen(QColor("#dc2626"), 0))
            for box in self.overflow:
                painter.fillRect(QRectF(*box), QColor(239, 68, 68, 90))
                painter.drawRect(QRectF(*box))
        finally:
            painter.restore()

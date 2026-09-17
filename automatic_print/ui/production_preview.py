from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PIL.ImageQt import ImageQt
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter, QPen, QTransform
from PySide6.QtWidgets import QWidget

from ..layout_engine import discover_images
from ..layout_engine.intake.metadata.images import print_dimensions
from ..layout_engine.intake.preparation.item_factory import read_items
from ..layout_engine.labeling.base.labels import format_label, settings_label_badge
from ..layout_engine.labeling.base.dynamic_label import source_label_badge
from ..layout_engine.labeling.platform.platform_label import numbered_template
from ..layout_engine.labeling.markers.qr_detection import detect_qr_location


class ProductionPreview(QWidget):
    """A local thumbnail with decorations placed by the production engine."""

    def __init__(self, settings_getter, parent=None):
        super().__init__(parent)
        self.settings_getter = settings_getter
        self.path = None
        self.batch_name = ""
        self.thumbnail = QImage()
        self.badge = QImage()
        self.item = None
        self.detail = "选择本地图片文件夹后，自动显示生产图、标签和色块。"
        self.setMinimumHeight(300)

    def use_folder(self, folder):
        if not str(folder).strip():
            self.set_sample(None)
            return
        folder = Path(folder)
        paths = discover_images(folder) if folder.is_dir() else []
        sample = paths[0] if paths else None
        self.set_sample(sample, folder.name)

    def set_sample(self, path, batch_name=""):
        path = Path(path) if path else None
        self.batch_name = str(batch_name or (path.parent.name if path else ""))
        if path == self.path and not self.thumbnail.isNull():
            self.refresh()
            return
        self.path, self.item = path, None
        self.setToolTip(str(path) if path else "尚未选择生产图片")
        self.thumbnail = QImage()
        if path is not None:
            reader = QImageReader(str(path))
            size = reader.size()
            if size.isValid():
                reader.setScaledSize(size.scaled(QSize(900, 900), Qt.KeepAspectRatio))
            self.thumbnail = reader.read()
        self.refresh()

    def sample_text(self):
        settings = self.settings_getter()
        return format_label(
            numbered_template(settings), 1, self.path or Path("样板.png"),
            datetime.now().astimezone(), settings.label_date_format,
            settings.machine_number, 1,
            batch_name=self.batch_name,
        )

    def refresh(self, *_args):
        self.item, self.badge = None, QImage()
        if self.path is None or self.thumbnail.isNull():
            self.detail = "选择本地图片文件夹后，自动显示生产图、标签和色块。"
            self.update()
            return
        try:
            settings = replace(
                self.settings_getter(), allow_rotation=False,
                label_batch_name=self.batch_name,
            )
            choices, labels = read_items([self.path], settings, None)
            self.item = choices[0][0]
            if settings.number_images:
                badge = source_label_badge(labels[1], settings, self.path, self.item.rotation_degrees)
                self.badge = QImage(ImageQt(badge)).copy()
                badge.close()
            size = print_dimensions(self.path, self.settings_getter().dpi)
            source = "图片内嵌 DPI" if size.embedded_dpi else "缺少 DPI：尺寸为估算，不能用于切膜生产"
            qr = ""
            if settings.number_images and settings.label_follow_qr and settings.label_position != "block_below":
                qr = " · 膜标签已定位" if detect_qr_location(self.path) else " · 未找到膜标签，使用设定位置"
            self.detail = f"{size.width_mm:.1f} × {size.height_mm:.1f} 毫米 · {source}{qr}"
            if settings.label_detect_region:
                self.detail += f" · 膜标签已识别 · 文字区 {self.item.label_width*25.4/settings.dpi:.1f} × {self.item.label_height*25.4/settings.dpi:.1f} 毫米"
            elif settings.label_fit_height:
                self.detail += f" · 整段文字高度 ≤ {settings.label_reference_height_mm:g} 毫米"
            elif settings.label_position == "block_below":
                self.detail += " · 标签固定于色块下方"
        except (OSError, ValueError) as error:
            self.item = None
            self.detail = f"样板读取失败：{error}"
        self.update()

    def paintEvent(self, _event):
        painter = QPainter()
        if not painter.begin(self):
            return
        try:
            painter.fillRect(self.rect(), QColor("#f8fafc"))
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            if self.item is not None:
                self._checkerboard(painter)
                self._draw_sample(painter)
            painter.setPen(QColor("#475569"))
            painter.drawText(
                QRectF(12, self.height() - 52, self.width() - 24, 46),
                Qt.AlignCenter | Qt.TextWordWrap, self.detail,
            )
        finally:
            painter.end()

    def _draw_sample(self, painter):
        item = self.item
        scale = min(
            (self.width() - 32) / item.footprint_width,
            (self.height() - 70) / item.footprint_height,
        )
        painter.save()
        try:
            painter.translate(
                (self.width() - item.footprint_width * scale) / 2,
                (self.height() - 60 - item.footprint_height * scale) / 2,
            )
            painter.scale(scale, scale)
            image_rect = QRectF(item.image_rx, item.image_ry, item.width, item.height)
            painter.drawImage(image_rect, self.thumbnail.transformed(QTransform().rotate(-item.rotation_degrees)))
            painter.setPen(QPen(QColor("#cbd5e1"), 0))
            painter.drawRect(image_rect)
            if not self.badge.isNull():
                painter.drawImage(
                    QRectF(item.label_rx, item.label_ry, item.label_width, item.label_height),
                    self.badge,
                )
            if item.block_width:
                painter.fillRect(
                    QRectF(item.block_rx, item.block_ry, item.block_width, item.block_height),
                    QColor(self.settings_getter().color_block_color),
                )
        finally:
            painter.restore()

    def _checkerboard(self, painter):
        for y in range(8, self.height() - 60, 12):
            for x in range(8, self.width() - 8, 12):
                color = "#e2e8f0" if ((x - 8) // 12 + (y - 8) // 12) % 2 else "#ffffff"
                painter.fillRect(QRectF(x, y, 12, 12), QColor(color))

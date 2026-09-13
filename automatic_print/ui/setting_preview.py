from __future__ import annotations

from datetime import datetime
import re

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget


class SettingPreview(QWidget):
    def __init__(self, kind: str, values, parent=None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.values = values
        self.setMinimumHeight(230)

    def sample_text(self) -> str:
        template = self.values().get("text", "{编号}")
        if self.values().get('sequence_enabled') and not any(t in template for t in ('{编号}', '{number}')):
            template += ' {编号}'
        today = datetime.now().strftime(
            self.values().get("date_format") or "%Y-%m-%d"
        )
        replacements = {
            "{编号}": "12",
            "{日期}": today,
            "{完整文件名}": "B9UV77Y-黑色-XL-NO1-1.png",
            "{文件名}": "B9UV77Y-黑色-XL-NO1-1",
            "{number}": "12",
            "{date}": today,
            "{filename}": "B9UV77Y-黑色-XL-NO1-1.png",
            "{stem}": "B9UV77Y-黑色-XL-NO1-1",
            "{机器号}": self.values().get("machine_number", "M1").upper(),
        }
        for field, value in replacements.items():
            template = template.replace(field, value)
        return re.sub(r"_{2,}", "", template) or "（空文字）"

    def paintEvent(self, _event) -> None:
        painter = QPainter()
        if not painter.begin(self):
            return
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.fillRect(self.rect(), QColor("#f3f4f6"))
            frame = QRectF(8, 8, self.width() - 16, self.height() - 16)
            painter.setPen(QPen(QColor("#cbd5e1"), 1))
            painter.setBrush(QColor("#ffffff"))
            painter.drawRoundedRect(frame, 8, 8)
            image = self._image_rect()
            self._draw_image(painter, image)
            if self.kind == "label":
                self._draw_label(painter, image)
                if self.values().get('enabled') and self.values().get('platform_name'):
                    from .platform_preview import draw_platform_diagram
                    draw_platform_diagram(self, painter, image)
            else:
                self._draw_block(painter, image)
            painter.setPen(QColor("#64748b"))
            caption_font = QFont()
            caption_font.setPointSize(9)
            painter.setFont(caption_font)
            painter.drawText(
                QRectF(20, self.height() - 36, self.width() - 40, 22),
                Qt.AlignmentFlag.AlignCenter,
                self._caption(),
            )
        finally:
            painter.end()

    def _caption(self) -> str:
        values = self.values()
        if self.kind == "block":
            size = f"{values['width']:g} × {values['height']:g} 毫米"
        else:
            size = f"文字 {values['font_size']:g} 毫米"
        return f"{size} · 位置与大小实时预览（示意图）"

    def _image_rect(self) -> QRectF:
        width = max(160, self.width() - 290)
        return QRectF((self.width() - width) / 2, 35, width, 120)

    @staticmethod
    def _draw_image(painter: QPainter, image: QRectF) -> None:
        painter.setPen(QPen(QColor("#2563eb"), 2))
        painter.setBrush(QColor("#dbeafe"))
        painter.drawRoundedRect(image, 5, 5)
        painter.setPen(QColor("#1e3a8a"))
        painter.setFont(QFont("", 11))
        painter.drawText(image, Qt.AlignmentFlag.AlignCenter, "生产图片")

    def _draw_label(self, painter: QPainter, image: QRectF) -> None:
        values = self.values()
        if not values["enabled"]:
            self._disabled(painter, image, "标签已关闭")
            return
        if values["follow_qr"]:
            qr = QRectF(image.left() + 12, image.center().y() - 16, 32, 32)
            self._draw_qr(painter, qr)
            position = "left"
            anchor_y = qr.center().y()
        else:
            position = values["position"]
            anchor_y = image.center().y()
        font = QFont()
        font.setPixelSize(max(9, min(36, round(values["font_size"] * 1.4))))
        painter.setFont(font)
        metrics = QFontMetrics(font)
        text = self.sample_text()
        label_width = min(126, max(56, metrics.horizontalAdvance(text) + 18))
        label_height = metrics.height() + 12
        gap = min(55, values["gap"] * 1.4)
        rect = self._outside_rect(
            image, label_width, label_height, position, gap, anchor_y
        )
        if position == "block_below":
            block = QRectF(image.left() - 27, image.top(), 20, 20)
            painter.fillRect(block, QColor("#ff0000"))
            rect.moveTopLeft(block.bottomRight() - rect.bottomRight() + rect.topLeft())
            rect.moveTop(block.bottom() + gap)
        rect.translate(
            max(-70, min(70, values["offset_x"] * 1.2)),
            max(-70, min(70, values["offset_y"] * 1.2)),
        )
        painter.setPen(QColor("#111827"))
        shown = metrics.elidedText(
            text, Qt.TextElideMode.ElideRight, round(rect.width() - 12)
        )
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, shown)

    def _draw_block(self, painter: QPainter, image: QRectF) -> None:
        values = self.values()
        if not values["enabled"]:
            self._disabled(painter, image, "色块已关闭")
            return
        block_width = max(5, min(65, values["width"] * 2))
        block_height = max(5, min(90, values["height"] * 2))
        gap = min(55, values["gap"] * 1.4)
        positions = {
            "left_top": image.top(),
            "left": image.center().y() - block_height / 2,
            "left_bottom": image.bottom() - block_height,
        }
        x = image.left() - gap - block_width
        y = positions.get(values["position"], image.top())
        x += max(-70, min(gap, values["offset_x"] * 1.2))
        y += max(-70, min(70, values["offset_y"] * 1.2))
        rect = QRectF(x, y, block_width, block_height)
        painter.setPen(QPen(QColor("#7f1d1d"), 1))
        painter.setBrush(QColor(values["color"]))
        painter.drawRect(rect)

    @staticmethod
    def _outside_rect(image, width, height, position, gap, anchor_y):
        x_positions = {
            "left": image.left() - gap - width,
            "right": image.right() + gap,
        }
        if position in {"top", "top_left", "top_right"}:
            y = image.top() - gap - height
        elif position in {"bottom", "bottom_left", "bottom_right"}:
            y = image.bottom() + gap
        else:
            y = anchor_y - height / 2
        if position.endswith("_left"):
            x = image.left()
        elif position.endswith("_right"):
            x = image.right() - width
        else:
            x = x_positions.get(position, image.center().x() - width / 2)
        return QRectF(x, y, width, height)

    @staticmethod
    def _draw_qr(painter: QPainter, rect: QRectF) -> None:
        painter.setPen(QPen(QColor("#111827"), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(rect)
        painter.setBrush(QColor("#111827"))
        size = rect.width() / 5
        for column, row in ((0, 0), (3, 0), (0, 3), (2, 2), (4, 4)):
            painter.drawRect(
                QRectF(
                    rect.left() + column * size,
                    rect.top() + row * size,
                    size,
                    size,
                )
            )

    @staticmethod
    def _disabled(painter: QPainter, image: QRectF, text: str) -> None:
        painter.setPen(QColor("#64748b"))
        painter.setFont(QFont("", 10))
        painter.drawText(
            image,
            Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            text,
        )

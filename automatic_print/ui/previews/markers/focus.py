"""Large label-area inspection built from the already rendered production example."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QComboBox, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout


CASE_NAMES = (
    "膜标签在左 · 不旋转",
    "膜标签在右 · 不旋转",
    "膜标签在左 · 向左旋转90°",
    "膜标签在右 · 向左旋转90°",
)


class LabelFocusPreview(QGroupBox):
    """Show one exact label neighbourhood without shrinking the whole image."""

    def __init__(self, parent=None):
        super().__init__("标签局部放大预览 · 真实像素区域", parent)
        self.images: list[QImage] = []
        self.selector = QComboBox()
        self.selector.addItems(CASE_NAMES)
        self.selector.currentIndexChanged.connect(self.draw)
        self.note = QLabel(
            "只放大屏幕显示，不改变打印字号、标签位置或实际排版宽度。"
        )
        self.note.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.picture = QLabel("等待标签位置预览…")
        self.picture.setAlignment(Qt.AlignCenter)
        self.picture.setMinimumHeight(360)
        self.picture.setStyleSheet(
            "QLabel { background: #ffffff; border: 2px solid #a21caf; padding: 8px; }"
        )
        controls = QHBoxLayout()
        controls.addWidget(QLabel("查看情况"))
        controls.addWidget(self.selector)
        controls.addWidget(self.note, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.picture)

    def set_results(self, results, rendered_images):
        self.images = [label_area(image, data) for image, data in zip(rendered_images, results)]
        preferred = next(
            (index for index, row in enumerate(results)
             if row.get("production") and row.get("label_text")),
            next((index for index, row in enumerate(results) if row.get("label_text")), 0),
        )
        self.selector.setCurrentIndex(preferred)
        self.draw()

    def failed(self, text):
        if self.images:
            return
        self.picture.setPixmap(QPixmap())
        self.picture.setText("标签局部预览暂不可用\n" + text)

    def draw(self, *_args):
        index = self.selector.currentIndex()
        if index < 0 or index >= len(self.images):
            return
        target = self.picture.size()
        target.setWidth(max(320, target.width() - 20))
        target.setHeight(max(240, target.height() - 20))
        self.picture.setText("")
        self.picture.setPixmap(QPixmap.fromImage(self.images[index]).scaled(
            target, Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.draw()


def label_area(image: QImage, data) -> QImage:
    """Crop the source card and production label from the rendered example."""
    item = data.get("item")
    if item is None or not data.get("label_text") or not item.label_width:
        return image.copy()
    # render_example scales the complete production footprint into a bounded
    # screen image and lifts a negative external marker above y=0. Convert the
    # production coordinates into those rendered pixels before cropping.
    scale = image.width() / max(1, item.footprint_width)
    top = min(0, item.block_ry)

    def rendered_rect(x, y, width, height):
        return QRectF(x * scale, (y - top) * scale, width * scale, height * scale)

    region = data["region"]
    card = rendered_rect(
        item.image_rx + region.left * item.width,
        item.image_ry + region.top * item.height,
        (region.right - region.left) * item.width,
        (region.bottom - region.top) * item.height,
    )
    label = rendered_rect(
        item.label_rx, item.label_ry, item.label_width, item.label_height
    )
    # A detected light header may span most of the source width. Keep only the
    # card edge immediately around the label; the full four-case image below
    # remains the authority for the overall knife/card relationship.
    reach = max(24.0, label.height() * 1.5)
    nearby_card = card.intersected(label.adjusted(-reach, -reach, reach, reach))
    area = label.united(nearby_card) if not nearby_card.isEmpty() else label
    padding = max(18.0, min(area.width(), area.height()) * 0.18)
    area = area.adjusted(-padding, -padding, padding, padding)
    area = area.intersected(QRectF(0, 0, image.width(), image.height()))
    return image.copy(area.toAlignedRect())

"""Large label inspection rendered directly from a real source image."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout,
)


CASE_NAMES = (
    "膜标签在左 · 不旋转",
    "膜标签在右 · 不旋转",
    "膜标签在左 · 向左旋转90°",
    "膜标签在右 · 向左旋转90°",
)


class LabelFocusPreview(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("真实位置关系 · 刀码＋膜标签＋文字标签", parent)
        self.images: list[QImage] = []
        self.results = []
        self.selector = QComboBox()
        self.selector.addItems(CASE_NAMES)
        self.selector.currentIndexChanged.connect(self.draw)
        self.note = QLabel("等待当前批次真实图片…")
        self.note.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.readout = QLabel("标签文字：等待预览…")
        self.readout.setTextFormat(Qt.PlainText)
        self.readout.setWordWrap(True)
        self.readout.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.readout.setMinimumHeight(110)
        self.readout.setStyleSheet(
            "QLabel { color: #111827; background: #ffffff; font-size: 32px; "
            "font-weight: 700; padding: 12px; border: 3px solid #a21caf; }"
        )
        self.picture = QLabel("等待标签位置预览…")
        self.picture.setAlignment(Qt.AlignCenter)
        self.picture.setStyleSheet("QLabel { background: #ffffff; }")
        self.scroll = QScrollArea()
        self.scroll.setAlignment(Qt.AlignCenter)
        self.scroll.setWidget(self.picture)
        self.scroll.setWidgetResizable(False)
        self.scroll.setMinimumHeight(360)
        self.scroll.setStyleSheet("QScrollArea { border: 3px solid #a21caf; }")
        controls = QHBoxLayout()
        controls.addWidget(QLabel("查看情况"))
        controls.addWidget(self.selector)
        controls.addWidget(self.note, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.readout)
        layout.addWidget(self.scroll)

    def set_results(self, results):
        self.results = list(results)
        self.images = []
        for row in results:
            width, height = row.get("focus_size", (0, 0))
            pixels = row.get("focus_pixels", b"")
            self.images.append(
                QImage(pixels, width, height, QImage.Format_RGBA8888).copy())
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
        if index < 0 or index >= len(self.images) or self.images[index].isNull():
            return
        row = self.results[index]
        if row.get("production"):
            source = "当前批次真实生产图"
        elif str(row.get("sample_kind", "")).startswith("haloo"):
            source = "代码库内置真实 Haloo 样本"
        else:
            source = "代码方向示意（无可用真实图片）"
        self.note.setText(source + " · 三者按真实坐标显示 · 紫色连线为文字放大镜")
        self.readout.setText("标签文字放大阅读（可复制）：\n" +
                             str(row.get("label_text", "")))
        self.picture.setText("")
        target_width = max(900, self.scroll.viewport().width()-12)
        self.picture.setPixmap(QPixmap.fromImage(self.images[index]).scaledToWidth(
            target_width, Qt.SmoothTransformation))
        self.picture.adjustSize()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.draw()

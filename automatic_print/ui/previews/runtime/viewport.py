"""GUI-only zoom and expanded inspection shared by production previews."""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSpinBox, QLabel, QDialog,
)


class PreviewViewport(QWidget):
    def __init__(self, preview, scroll, parent=None):
        super().__init__(parent)
        self.preview, self.scroll, self.dialog = preview, scroll, None
        self.asset_zoom = 100
        preview.view_controls = self
        self.zoom = QSpinBox()
        self.zoom.setRange(25, 400)
        self.zoom.setValue(100)
        self.zoom.setSingleStep(25)
        self.zoom.setSuffix('%')
        self.zoom.setToolTip('仅放大查看，不改变图片打印尺寸或重新排版。')
        bar = QHBoxLayout()
        bar.addWidget(QLabel('预览缩放'))
        for text, callback in (
            ('缩小', lambda: self.zoom.setValue(self.zoom.value()-25)),
            ('放大', lambda: self.zoom.setValue(self.zoom.value()+25)),
            ('适合宽度', lambda: self.zoom.setValue(100)),
        ):
            button = QPushButton(text)
            button.clicked.connect(callback)
            bar.addWidget(button)
        bar.addWidget(self.zoom)
        self.expand = QPushButton('最大化查看')
        self.expand.clicked.connect(self.toggle_expanded)
        bar.addWidget(self.expand)
        bar.addStretch()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(bar)
        layout.addWidget(scroll, 1)
        scroll.viewport().installEventFilter(self)
        self.zoom.valueChanged.connect(self.zoom_changed)

    def zoom_changed(self, value):
        if self.preview.overview and value > self.asset_zoom:
            self.preview.images.clear()
            self.preview.badges.clear()
        self.asset_zoom = value
        self.update_geometry()

    def scale(self):
        width = max(1, self.scroll.viewport().width()-32)
        return width/max(1, self.preview.canvas_width)*self.zoom.value()/100

    def update_geometry(self, *_args):
        preview = self.preview
        if preview.item is None:
            preview.setMinimumSize(0, 440)
            return
        width = max(1, self.scroll.viewport().width())
        preview.setMinimumWidth(max(0, round((width-32)*self.zoom.value()/100)+32)
                                if self.zoom.value() > 100 else 0)
        preview.setMinimumHeight(max(440, round(preview.canvas_height*self.scale())+110))
        preview.update()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Resize:
            self.update_geometry()
        if event.type() == QEvent.Wheel and event.modifiers() & Qt.ControlModifier:
            self.zoom.setValue(self.zoom.value()+(25 if event.angleDelta().y() > 0 else -25))
            return True
        return super().eventFilter(watched, event)

    def toggle_expanded(self):
        if self.dialog:
            self.dialog.close()
            return
        self.origin = self.parentWidget().layout()
        self.origin_index = self.origin.indexOf(self)
        self.origin.removeWidget(self)
        dialog = QDialog(self.window())
        dialog.setWindowTitle('整批排版预览 · 放大检查')
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowMinMaxButtonsHint)
        QVBoxLayout(dialog).addWidget(self)
        self.dialog = dialog
        self.scroll.setMinimumHeight(0)
        self.scroll.setMaximumHeight(16777215)
        self.expand.setText('返回主界面')
        dialog.finished.connect(self.restore)
        dialog.showMaximized()

    def restore(self, *_args):
        dialog, self.dialog = self.dialog, None
        dialog.layout().removeWidget(self)
        self.origin.insertWidget(self.origin_index, self)
        self.scroll.setMinimumHeight(420)
        self.scroll.setMaximumHeight(460)
        self.expand.setText('最大化查看')
        self.show()
        self.update_geometry()
        dialog.deleteLater()


def resize_legacy_preview(preview) -> None:
    """Size a preview that has not yet been wrapped by PreviewViewport."""
    if preview.overview and preview.item is not None:
        height = max(
            440,
            round(preview.canvas_height * (preview.width() - 32)
                  / preview.canvas_width) + 110,
        )
        if preview.minimumHeight() != height:
            preview.setMinimumHeight(height)


def resize_preview(preview) -> None:
    controls = getattr(preview, 'view_controls', None)
    if controls is not None:
        controls.update_geometry()
    else:
        resize_legacy_preview(preview)

"""Direct source-image actions for recoverable per-image diagnostics."""
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


class ImageAnomalyActions(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setMaximumHeight(180)
        self.container = QWidget()
        self.rows = QVBoxLayout(self.container)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.setWidget(self.container)
        self.hide()

    def clear(self):
        while self.rows.count():
            item = self.rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.hide()

    def show_rows(self, anomalies, folder=None):
        self.clear()
        for row in anomalies:
            source = row.get('path')
            if not source and folder and row.get('source'):
                source = str(Path(folder) / row['source'])
            if not source:
                continue
            line = QWidget(self.container)
            layout = QHBoxLayout(line)
            layout.setContentsMargins(0, 0, 0, 0)
            name = QLabel(row.get('source') or Path(source).name)
            name.setToolTip(f"{source}\n{row.get('kind', '')}")
            button = QPushButton('打开原图')
            button.setToolTip(str(source))
            button.clicked.connect(lambda _checked=False, path=source: self.open_image(path))
            layout.addWidget(name, 1)
            layout.addWidget(button)
            self.rows.addWidget(line)
        self.setVisible(self.rows.count() > 0)

    def open_image(self, path):
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(self, '无法打开原图', f'请检查图片文件是否仍在原位置：\n{path}')

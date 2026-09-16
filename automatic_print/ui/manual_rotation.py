import json
from pathlib import Path

from PySide6.QtWidgets import QWidget, QComboBox, QPushButton, QHBoxLayout


class ManualRotationPanel(QWidget):
    """Per-source overrides; asynchronous whole-batch checks report unsafe choices."""

    def __init__(self, window, preview, parent=None):
        super().__init__(parent)
        self.window, self.preview = window, preview
        self.images = QComboBox()
        self.images.currentIndexChanged.connect(self.show_selected)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.images, 1)
        for title, change in (("向左旋转", 90), ("向右旋转", -90), ("还原图片", None)):
            button = QPushButton(title)
            button.clicked.connect(lambda _checked=False, step=change: self.apply(step))
            layout.addWidget(button)
        window.folder.textChanged.connect(self.use_folder)
        preview.sources_ready.connect(self.populate)

    def use_folder(self, folder):
        self.images.blockSignals(True)
        self.images.clear()
        self.images.blockSignals(False)

    def populate(self, paths):
        self.images.blockSignals(True)
        self.images.clear()
        for path in paths:
            self.images.addItem(path.name, str(path.resolve()))
        self.images.blockSignals(False)

    def show_selected(self, *_args):
        self.preview.set_sample(self.images.currentData())

    def apply(self, step):
        path = self.images.currentData()
        if not path:
            return
        preferences = self.window.preferences
        rotations = json.loads(preferences.value("layout/manual_rotations", "{}", str))
        rotations[path] = (rotations.get(path, 0) + step) % 360 if step is not None else 0
        if rotations[path] == 270:
            rotations[path] = -90
        preferences.setValue("layout/manual_rotations", json.dumps(rotations))
        preferences.sync()
        self.preview.invalidate_parameters()

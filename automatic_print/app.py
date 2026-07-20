from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .layout import LayoutSettings, discover_images, generate_layouts


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Automatic Print")
        self.resize(620, 360)

        self.folder = QLineEdit()
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.choose_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder)
        folder_row.addWidget(browse)

        self.width = self._double_box(600, 50, 5000)
        self.spacing = self._double_box(3, 0, 100)
        self.margin = self._double_box(3, 0, 100)
        self.max_length = self._double_box(2000, 100, 50000)
        self.dpi = QSpinBox()
        self.dpi.setRange(72, 1200)
        self.dpi.setValue(300)

        form = QFormLayout()
        form.addRow("Image folder", folder_row)
        form.addRow("Media width (mm)", self.width)
        form.addRow("Image spacing (mm)", self.spacing)
        form.addRow("Outer margin (mm)", self.margin)
        form.addRow("Maximum file length (mm)", self.max_length)
        form.addRow("Output DPI", self.dpi)

        self.status = QLabel("Choose a folder to begin.")
        generate = QPushButton("Generate print files")
        generate.clicked.connect(self.generate)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addStretch()
        layout.addWidget(self.status)
        layout.addWidget(generate)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    @staticmethod
    def _double_box(value: float, minimum: float, maximum: float) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setDecimals(1)
        box.setValue(value)
        return box

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose image folder")
        if folder:
            self.folder.setText(folder)

    def generate(self) -> None:
        source = Path(self.folder.text().strip())
        if not source.is_dir():
            QMessageBox.warning(self, "Folder required", "Choose a valid image folder.")
            return
        images = discover_images(source)
        if not images:
            QMessageBox.warning(self, "No images", "No supported images were found.")
            return

        settings = LayoutSettings(
            media_width_mm=self.width.value(),
            spacing_mm=self.spacing.value(),
            margin_mm=self.margin.value(),
            dpi=self.dpi.value(),
            max_length_mm=self.max_length.value(),
        )
        base = Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation))
        job_id = datetime.now().strftime("JOB_%Y%m%d_%H%M%S")
        output = base / "Automatic Print" / job_id
        try:
            pages = generate_layouts(images, output, settings)
            manifest = {
                "job_id": job_id,
                "created_at": datetime.now().astimezone().isoformat(),
                "source_folder": str(source),
                "settings": asdict(settings),
                "source_count": len(images),
                "pages": pages,
            }
            (output / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )
        except Exception as error:
            QMessageBox.critical(self, "Generation failed", str(error))
            return

        self.status.setText(f"Created {len(pages)} file(s) in {output}")
        QMessageBox.information(self, "Finished", f"Print files created in:\n{output}")


def run() -> int:
    application = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return application.exec()

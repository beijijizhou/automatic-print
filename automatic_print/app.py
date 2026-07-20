from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QObject,
    Qt,
    QSettings,
    QStandardPaths,
    QThread,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .layout import LayoutSettings, discover_images, generate_layout
from .updater import UpdateInfo, fetch_latest_release, version_tuple


class GenerateWorker(QObject):
    progress = Signal(str, int, int, str)
    finished = Signal(str, object)
    failed = Signal(str)

    def __init__(
        self,
        images: list[Path],
        source: Path,
        output: Path,
        job_id: str,
        settings: LayoutSettings,
    ) -> None:
        super().__init__()
        self.images = images
        self.source = source
        self.output = output
        self.job_id = job_id
        self.settings = settings

    @Slot()
    def run(self) -> None:
        try:
            print_image = generate_layout(
                self.images, self.output, self.settings, self.progress.emit
            )
            manifest = {
                "job_id": self.job_id,
                "created_at": datetime.now().astimezone().isoformat(),
                "source_folder": str(self.source),
                "settings": asdict(self.settings),
                "source_count": len(self.images),
                "print_image": print_image,
            }
            (self.output / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.finished.emit(str(self.output), print_image)


class UpdateWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(fetch_latest_release())
        except Exception as error:
            self.failed.emit(str(error))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Automatic Print")
        self.resize(720, 470)
        self.thread: QThread | None = None
        self.worker: GenerateWorker | None = None
        self.update_thread: QThread | None = None
        self.update_worker: UpdateWorker | None = None
        self.update_is_silent = True
        self.started_at: float | None = None
        self.stage_started_at: float | None = None
        self.current_stage = ""
        self.current_count = 0
        self.current_total = 0
        self.current_percent = 0
        self.active_fast_png = True
        self.preferences = QSettings("AutomaticPrint", "AutomaticPrint")
        self.clock = QTimer(self)
        self.clock.setInterval(1000)
        self.clock.timeout.connect(self.refresh_timing)

        self.folder = QLineEdit()
        browse = QPushButton("Browse…")
        browse.clicked.connect(self.choose_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder)
        folder_row.addWidget(browse)

        self.width = self._double_box(600, 50, 5000)
        self.spacing = self._double_box(3, 0, 100)
        self.margin = self._double_box(3, 0, 100)
        self.dpi = QSpinBox()
        self.dpi.setRange(72, 1200)
        self.dpi.setValue(300)
        self.worker_threads = QSpinBox()
        self.worker_threads.setRange(1, 32)
        self.worker_threads.setValue(8)
        self.fast_png = QCheckBox("Fast PNG (larger file, same image quality)")
        self.fast_png.setChecked(True)

        form = QFormLayout()
        form.addRow("Image folder", folder_row)
        form.addRow("Media width (mm)", self.width)
        form.addRow("Image spacing (mm)", self.spacing)
        form.addRow("Outer margin (mm)", self.margin)
        form.addRow("Output DPI", self.dpi)
        form.addRow("Parallel image workers", self.worker_threads)
        form.addRow("PNG mode", self.fast_png)

        default_output = QStandardPaths.writableLocation(QStandardPaths.DesktopLocation)
        saved_output = self.preferences.value("output_location", default_output, str)
        self.output_location = QLineEdit(saved_output)
        output_browse = QPushButton("Browse…")
        output_browse.clicked.connect(self.choose_output_location)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_location)
        output_row.addWidget(output_browse)
        form.addRow("Save jobs in", output_row)

        self.job_path = QLineEdit()
        self.job_path.setReadOnly(True)
        self.job_path.setPlaceholderText("The new job folder will appear here")
        form.addRow("New job folder", self.job_path)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Not started")
        self.status = QLabel("Choose a folder to begin.")
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.current_file = QLabel("Current file: —")
        self.current_file.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.run_log = QPlainTextEdit()
        self.run_log.setReadOnly(True)
        self.run_log.setMaximumHeight(115)
        self.run_log.setPlaceholderText("Copyable timing details will appear here")
        self.generate_button = QPushButton("Generate one PNG print image")
        self.generate_button.clicked.connect(self.generate)
        self.version_label = QLabel(f"Version {__version__}")
        self.check_update_button = QPushButton("Check for updates")
        self.check_update_button.clicked.connect(lambda: self.check_for_updates(False))
        version_row = QHBoxLayout()
        version_row.addWidget(self.version_label)
        version_row.addStretch()
        version_row.addWidget(self.check_update_button)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addStretch()
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addWidget(self.current_file)
        layout.addWidget(self.run_log)
        layout.addWidget(self.generate_button)
        layout.addLayout(version_row)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        QTimer.singleShot(2500, lambda: self.check_for_updates(True))

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

    def choose_output_location(self) -> None:
        starting_folder = self.output_location.text().strip()
        folder = QFileDialog.getExistingDirectory(
            self, "Choose where to save print jobs", starting_folder
        )
        if folder:
            self.output_location.setText(folder)
            self.preferences.setValue("output_location", folder)

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
            fast_png=self.fast_png.isChecked(),
            worker_threads=self.worker_threads.value(),
        )
        base = Path(self.output_location.text().strip())
        if not base.is_dir():
            QMessageBox.warning(
                self, "Output folder required", "Choose a valid output folder."
            )
            return
        self.preferences.setValue("output_location", str(base))
        job_id = datetime.now().strftime("JOB_%Y%m%d_%H%M%S")
        output = base / job_id
        self.job_path.setText(str(output))
        self.status.setText(f"Found {len(images)} images. Starting…")
        self.current_file.setText("Current file: —")
        self.progress.setValue(0)
        self.progress.setFormat("Starting…")
        self.run_log.clear()
        self.run_log.appendPlainText(f"Job: {job_id}")
        self.run_log.appendPlainText(f"Images: {len(images)}")
        self.run_log.appendPlainText(f"Output: {output}")
        self.generate_button.setEnabled(False)
        self.started_at = time.monotonic()
        self.active_fast_png = settings.fast_png
        self.stage_started_at = self.started_at
        self.current_stage = "Starting"
        self.current_count = 0
        self.current_total = len(images)
        self.current_percent = 0
        self.clock.start()

        self.thread = QThread(self)
        self.worker = GenerateWorker(images, source, output, job_id, settings)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.generation_finished)
        self.worker.failed.connect(self.generation_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.clear_worker)
        self.thread.start()

    @Slot(str, int, int, str)
    def update_progress(self, stage: str, current: int, total: int, filename: str) -> None:
        # Reading and combining each use 45%; saving the PNG uses the final 10%.
        if stage == "Reading image sizes":
            percent = round((current / total) * 45)
        elif stage == "Combining images":
            percent = 45 + round((current / total) * 45)
        else:
            percent = 95
        if stage != self.current_stage:
            self.stage_started_at = time.monotonic()
            self.run_log.appendPlainText(f"Started: {stage}")
        self.current_stage = stage
        self.current_count = current
        self.current_total = total
        self.current_percent = percent
        if stage == "Saving PNG":
            self.progress.setRange(0, 0)
            self.progress.setFormat("Saving PNG…")
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(percent)
            self.progress.setFormat(f"{percent}% — {stage}")
        self.current_file.setText(f"Current file: {filename}")
        self.refresh_timing()

    @Slot()
    def refresh_timing(self) -> None:
        now = time.monotonic()
        elapsed = now - self.started_at if self.started_at else 0
        stage_elapsed = now - self.stage_started_at if self.stage_started_at else 0
        if (
            self.current_stage in {"Reading image sizes", "Combining images"}
            and self.current_count > 0
        ):
            remaining_items = self.current_total - self.current_count
            remaining = (stage_elapsed / self.current_count) * remaining_items
            estimate = f"This stage about {self._duration(remaining)} left"
        elif self.current_stage == "Saving PNG":
            rate_key = (
                "fast_png_seconds_per_megapixel"
                if self.active_fast_png
                else "normal_png_seconds_per_megapixel"
            )
            saved_rate = float(self.preferences.value(rate_key, 0))
            megapixels = self.current_total / 1_000_000
            if saved_rate > 0 and megapixels > 0:
                expected = saved_rate * megapixels
                remaining = max(0, expected - stage_elapsed)
                estimate = f"Based on the last job: about {self._duration(remaining)} left"
            else:
                estimate = "No reliable estimate yet; timing this save"
        else:
            estimate = "Calculating…"
        stage_progress = (
            self.current_stage
            if self.current_stage == "Saving PNG"
            else f"{self.current_stage}: {self.current_count} / {self.current_total}"
        )
        self.status.setText(
            f"{stage_progress}  ·  "
            f"Stage {self._duration(stage_elapsed)}  ·  "
            f"Total {self._duration(elapsed)}  ·  {estimate}"
        )

    @staticmethod
    def _duration(seconds: float) -> str:
        seconds = max(0, round(seconds))
        minutes, seconds = divmod(seconds, 60)
        return f"{minutes}m {seconds:02d}s" if minutes else f"{seconds}s"

    @Slot(str, object)
    def generation_finished(self, output: str, print_image: dict) -> None:
        self.clock.stop()
        timings = print_image["timings_seconds"]
        megapixels = (
            print_image["width_px"] * print_image["height_px"] / 1_000_000
        )
        if megapixels > 0:
            rate_key = (
                "fast_png_seconds_per_megapixel"
                if self.active_fast_png
                else "normal_png_seconds_per_megapixel"
            )
            self.preferences.setValue(
                rate_key, timings["saving_png"] / megapixels
            )
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress.setFormat("100% — Finished")
        self.status.setText(
            "Finished — "
            f"Read {self._duration(timings['reading'])} · "
            f"Combine {self._duration(timings['combining'])} · "
            f"Save PNG {self._duration(timings['saving_png'])} · "
            f"Total {self._duration(timings['total'])}"
        )
        self.current_file.setText("Current file: print.png")
        self.run_log.appendPlainText(
            f"Finished: Read {timings['reading']:.1f}s | "
            f"Combine {timings['combining']:.1f}s | "
            f"Save PNG {timings['saving_png']:.1f}s | "
            f"Total {timings['total']:.1f}s"
        )
        self.generate_button.setEnabled(True)
        QMessageBox.information(self, "Finished", f"PNG print image created in:\n{output}")

    @Slot(str)
    def generation_failed(self, message: str) -> None:
        self.clock.stop()
        self.progress.setRange(0, 100)
        self.progress.setFormat("Failed")
        self.status.setText("Generation failed.")
        self.run_log.appendPlainText(f"Failed: {message}")
        self.generate_button.setEnabled(True)
        QMessageBox.critical(self, "Generation failed", message)

    @Slot()
    def clear_worker(self) -> None:
        self.thread = None
        self.worker = None

    def check_for_updates(self, silent: bool) -> None:
        if self.update_thread is not None:
            return
        self.update_is_silent = silent
        self.check_update_button.setEnabled(False)
        self.check_update_button.setText("Checking…")
        self.update_thread = QThread(self)
        self.update_worker = UpdateWorker()
        self.update_worker.moveToThread(self.update_thread)
        self.update_thread.started.connect(self.update_worker.run)
        self.update_worker.finished.connect(self.update_check_finished)
        self.update_worker.failed.connect(self.update_check_failed)
        self.update_worker.finished.connect(self.update_thread.quit)
        self.update_worker.failed.connect(self.update_thread.quit)
        self.update_thread.finished.connect(self.update_worker.deleteLater)
        self.update_thread.finished.connect(self.update_thread.deleteLater)
        self.update_thread.finished.connect(self.clear_update_worker)
        self.update_thread.start()

    @Slot(object)
    def update_check_finished(self, update: UpdateInfo) -> None:
        if version_tuple(update.version) > version_tuple(__version__):
            answer = QMessageBox.question(
                self,
                "Update available",
                f"Automatic Print {update.version} is available.\n\n"
                f"Current version: {__version__}\n\n"
                "Open the installer download page now?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                QDesktopServices.openUrl(QUrl(update.download_url))
        elif not self.update_is_silent:
            QMessageBox.information(
                self,
                "No updates",
                f"Automatic Print {__version__} is the latest version.",
            )

    @Slot(str)
    def update_check_failed(self, message: str) -> None:
        if not self.update_is_silent:
            QMessageBox.warning(
                self,
                "Update check failed",
                f"Could not check for updates.\n\n{message}",
            )

    @Slot()
    def clear_update_worker(self) -> None:
        self.update_thread = None
        self.update_worker = None
        self.check_update_button.setEnabled(True)
        self.check_update_button.setText("Check for updates")


def run() -> int:
    application = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return application.exec()

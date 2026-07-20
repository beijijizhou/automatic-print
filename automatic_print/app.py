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
    QComboBox,
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
from .layout import (
    LayoutSettings,
    discover_images,
    discovered_extensions,
    generate_layout,
    png_engine_name,
)
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
        self.setWindowTitle("自动打印排版")
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
        self.active_png_compression = 1
        self.active_png_engine = png_engine_name()
        self.preferences = QSettings("AutomaticPrint", "AutomaticPrint")
        self.clock = QTimer(self)
        self.clock.setInterval(1000)
        self.clock.timeout.connect(self.refresh_timing)

        self.folder = QLineEdit()
        browse = QPushButton("选择图片文件夹…")
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
        self.png_compression = QComboBox()
        self.png_compression.addItem("等级 1 — 轻度压缩（推荐）", 1)
        self.png_compression.addItem("等级 0 — 不压缩（文件最大）", 0)
        self.png_compression.addItem("等级 3 — 中度压缩（文件更小）", 3)

        form = QFormLayout()
        form.addRow("图片文件夹", folder_row)
        form.addRow("材料宽度（毫米）", self.width)
        form.addRow("图片间距（毫米）", self.spacing)
        form.addRow("外边距（毫米）", self.margin)
        form.addRow("输出 DPI", self.dpi)
        form.addRow("并行处理线程数", self.worker_threads)
        form.addRow("PNG 压缩", self.png_compression)

        default_output = QStandardPaths.writableLocation(QStandardPaths.DesktopLocation)
        saved_output = self.preferences.value("output_location", default_output, str)
        self.output_location = QLineEdit(saved_output)
        output_browse = QPushButton("选择保存位置…")
        output_browse.clicked.connect(self.choose_output_location)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_location)
        output_row.addWidget(output_browse)
        form.addRow("任务保存位置", output_row)

        self.job_path = QLineEdit()
        self.job_path.setReadOnly(True)
        self.job_path.setPlaceholderText("开始生成后，这里会显示新任务文件夹")
        form.addRow("本次任务文件夹", self.job_path)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("尚未开始")
        self.status = QLabel("请选择包含图片的文件夹。")
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.current_file = QLabel("当前文件：—")
        self.current_file.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.run_log = QPlainTextEdit()
        self.run_log.setReadOnly(True)
        self.run_log.setMaximumHeight(115)
        self.run_log.setPlaceholderText("这里会显示可复制的运行记录和耗时")
        self.generate_button = QPushButton("生成单张 PNG 打印图片")
        self.generate_button.clicked.connect(self.generate)
        self.version_label = QLabel(f"版本 {__version__}")
        self.check_update_button = QPushButton("检查更新")
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
        folder = QFileDialog.getExistingDirectory(
            self, "请选择包含图片的文件夹（无需选择单张图片）"
        )
        if folder:
            self.folder.setText(folder)
            count = len(discover_images(Path(folder)))
            self.status.setText(f"已找到 {count} 张图片，可以开始生成。")

    def choose_output_location(self) -> None:
        starting_folder = self.output_location.text().strip()
        folder = QFileDialog.getExistingDirectory(
            self, "请选择打印任务的保存位置", starting_folder
        )
        if folder:
            self.output_location.setText(folder)
            self.preferences.setValue("output_location", folder)

    def generate(self) -> None:
        source = Path(self.folder.text().strip())
        if not source.is_dir():
            QMessageBox.warning(self, "请选择文件夹", "请选择有效的图片文件夹。")
            return
        images = discover_images(source)
        if not images:
            extensions = discovered_extensions(source)
            found_types = ", ".join(extensions[:15]) if extensions else "没有文件"
            QMessageBox.warning(
                self,
                "未找到图片",
                "所选文件夹及其子文件夹中没有找到支持的图片。\n\n"
                f"实际发现的文件类型：{found_types}\n\n"
                "支持格式：PNG、TIFF、JPG、JFIF、WebP、BMP",
            )
            return

        settings = LayoutSettings(
            media_width_mm=self.width.value(),
            spacing_mm=self.spacing.value(),
            margin_mm=self.margin.value(),
            dpi=self.dpi.value(),
            png_compression_level=self.png_compression.currentData(),
            worker_threads=self.worker_threads.value(),
        )
        base = Path(self.output_location.text().strip())
        if not base.is_dir():
            QMessageBox.warning(
                self, "请选择保存位置", "请选择有效的任务保存位置。"
            )
            return
        self.preferences.setValue("output_location", str(base))
        job_id = datetime.now().strftime("JOB_%Y%m%d_%H%M%S")
        output = base / job_id
        self.job_path.setText(str(output))
        self.status.setText(f"已找到 {len(images)} 张图片，正在开始…")
        self.current_file.setText("当前文件：—")
        self.progress.setValue(0)
        self.progress.setFormat("正在开始…")
        self.run_log.clear()
        self.run_log.appendPlainText(f"任务：{job_id}")
        self.run_log.appendPlainText(f"图片数量：{len(images)}")
        self.run_log.appendPlainText(f"输出位置：{output}")
        self.generate_button.setEnabled(False)
        self.started_at = time.monotonic()
        self.active_png_compression = settings.png_compression_level
        self.active_png_engine = png_engine_name()
        self.stage_started_at = self.started_at
        self.current_stage = "正在开始"
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
        if stage == "读取图片尺寸":
            percent = round((current / total) * 45)
        elif stage == "合成图片":
            percent = 45 + round((current / total) * 45)
        else:
            percent = 95
        if stage != self.current_stage:
            self.stage_started_at = time.monotonic()
            self.run_log.appendPlainText(f"开始：{stage}")
        self.current_stage = stage
        self.current_count = current
        self.current_total = total
        self.current_percent = percent
        if stage == "保存 PNG":
            self.progress.setRange(0, 0)
            self.progress.setFormat("正在保存 PNG…")
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(percent)
            self.progress.setFormat(f"{percent}% — {stage}")
        self.current_file.setText(f"当前文件：{filename}")
        self.refresh_timing()

    @Slot()
    def refresh_timing(self) -> None:
        now = time.monotonic()
        elapsed = now - self.started_at if self.started_at else 0
        stage_elapsed = now - self.stage_started_at if self.stage_started_at else 0
        if (
            self.current_stage in {"读取图片尺寸", "合成图片"}
            and self.current_count > 0
        ):
            remaining_items = self.current_total - self.current_count
            remaining = (stage_elapsed / self.current_count) * remaining_items
            estimate = f"本阶段预计还需 {self._duration(remaining)}"
        elif self.current_stage == "保存 PNG":
            rate_key = self._png_rate_key()
            saved_rate = float(self.preferences.value(rate_key, 0))
            megapixels = self.current_total / 1_000_000
            if saved_rate > 0 and megapixels > 0:
                expected = saved_rate * megapixels
                remaining = max(0, expected - stage_elapsed)
                estimate = f"根据上次任务，预计还需 {self._duration(remaining)}"
            else:
                estimate = "暂无可靠预计，正在记录本次保存速度"
        else:
            estimate = "正在计算…"
        stage_progress = (
            self.current_stage
            if self.current_stage == "保存 PNG"
            else f"{self.current_stage}: {self.current_count} / {self.current_total}"
        )
        self.status.setText(
            f"{stage_progress}  ·  "
            f"本阶段 {self._duration(stage_elapsed)}  ·  "
            f"总计 {self._duration(elapsed)}  ·  {estimate}"
        )

    @staticmethod
    def _duration(seconds: float) -> str:
        seconds = max(0, round(seconds))
        minutes, seconds = divmod(seconds, 60)
        return f"{minutes}分{seconds:02d}秒" if minutes else f"{seconds}秒"

    @Slot(str, object)
    def generation_finished(self, output: str, print_image: dict) -> None:
        self.clock.stop()
        timings = print_image["timings_seconds"]
        megapixels = (
            print_image["width_px"] * print_image["height_px"] / 1_000_000
        )
        if megapixels > 0:
            rate_key = self._png_rate_key()
            self.preferences.setValue(
                rate_key, timings["saving_png"] / megapixels
            )
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress.setFormat("100% — 已完成")
        self.status.setText(
            "已完成 — "
            f"读取 {self._duration(timings['reading'])} · "
            f"合成 {self._duration(timings['combining'])} · "
            f"保存 PNG {self._duration(timings['saving_png'])} · "
            f"总计 {self._duration(timings['total'])}"
        )
        self.current_file.setText("当前文件：print.png")
        self.run_log.appendPlainText(
            f"完成：读取 {timings['reading']:.1f}秒 | "
            f"合成 {timings['combining']:.1f}秒 | "
            f"保存 PNG {timings['saving_png']:.1f}秒 | "
            f"总计 {timings['total']:.1f}秒"
        )
        self.run_log.appendPlainText(
            f"输出：{print_image['width_px']} × {print_image['height_px']} 像素 | "
            f"实际长度 {print_image['height_mm'] / 1000:.2f}米 | "
            f"文件大小 {self._file_size(print_image['file_size_bytes'])} | "
            f"保存引擎 {print_image['png_engine']} | "
            f"PNG 压缩等级 {print_image['png_compression_level']} | "
            f"平均输出 {print_image['output_megabytes_per_second']:.1f} MB/s"
        )
        self.generate_button.setEnabled(True)
        QMessageBox.information(self, "生成完成", f"PNG 打印图片已保存到：\n{output}")

    @Slot(str)
    def generation_failed(self, message: str) -> None:
        self.clock.stop()
        self.progress.setRange(0, 100)
        self.progress.setFormat("生成失败")
        self.status.setText("生成失败。")
        self.run_log.appendPlainText(f"失败：{message}")
        self.generate_button.setEnabled(True)
        QMessageBox.critical(self, "生成失败", message)

    @staticmethod
    def _file_size(size_bytes: int) -> str:
        if size_bytes >= 1_000_000_000:
            return f"{size_bytes / 1_000_000_000:.2f} GB"
        return f"{size_bytes / 1_000_000:.1f} MB"

    def _png_rate_key(self) -> str:
        engine = "libvips" if self.active_png_engine == "libvips" else "pillow"
        return (
            f"png_{engine}_level_{self.active_png_compression}"
            "_seconds_per_megapixel"
        )

    @Slot()
    def clear_worker(self) -> None:
        self.thread = None
        self.worker = None

    def check_for_updates(self, silent: bool) -> None:
        if self.update_thread is not None:
            return
        self.update_is_silent = silent
        self.check_update_button.setEnabled(False)
        self.check_update_button.setText("正在检查…")
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
                "发现新版本",
                f"自动打印排版 {update.version} 已发布。\n\n"
                f"当前版本：{__version__}\n\n"
                "是否打开安装程序下载页面？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                QDesktopServices.openUrl(QUrl(update.download_url))
        elif not self.update_is_silent:
            QMessageBox.information(
                self,
                "已经是最新版",
                f"自动打印排版 {__version__} 已经是最新版本。",
            )

    @Slot(str)
    def update_check_failed(self, message: str) -> None:
        if not self.update_is_silent:
            QMessageBox.warning(
                self,
                "检查更新失败",
                f"暂时无法检查更新。\n\n{message}",
            )

    @Slot()
    def clear_update_worker(self) -> None:
        self.update_thread = None
        self.update_worker = None
        self.check_update_button.setEnabled(True)
        self.check_update_button.setText("检查更新")


def run() -> int:
    application = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return application.exec()

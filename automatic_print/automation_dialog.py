from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QObject,
    QSettings,
    QStandardPaths,
    QThread,
    Qt,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .automation.batch_browser import (
    BatchRecord,
    download_selected_batches,
    load_batch_records,
    load_platform_order_status,
)
from .automation.platforms import ERP_PLATFORMS
from .layout import LayoutSettings, discover_images, generate_layout


class AutomationWorker(QObject):
    progress = Signal(str)
    batches_loaded = Signal(object)
    status_loaded = Signal(object)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        action: str,
        platform_name: str,
        output: Path | None = None,
        batch_numbers: list[str] | None = None,
        settings: LayoutSettings | None = None,
        sample_limit: int | None = None,
    ) -> None:
        super().__init__()
        self.action = action
        self.platform_name = platform_name
        self.output = output
        self.batch_numbers = batch_numbers or []
        self.settings = settings
        self.sample_limit = sample_limit

    @Slot()
    def run(self) -> None:
        try:
            if self.action == "list":
                self.progress.emit(
                    f"正在读取 {self.platform_name} 已生成批次…"
                )
                self.batches_loaded.emit(
                    load_batch_records(self.platform_name)
                )
            elif self.action in {"status", "status_and_list"}:
                self.progress.emit(
                    f"正在刷新 {self.platform_name} 平台状态…"
                )
                self.status_loaded.emit(
                    load_platform_order_status(
                        self.platform_name, self.progress.emit
                    )
                )
                if self.action == "status_and_list":
                    self.progress.emit(
                        f"{self.platform_name} 状态已读取，正在刷新生产批次…"
                    )
                    self.batches_loaded.emit(
                        load_batch_records(self.platform_name)
                    )
            elif self.action == "download":
                if self.output is None:
                    raise RuntimeError("请选择下载保存位置。")
                files = download_selected_batches(
                    self.platform_name,
                    self.batch_numbers,
                    self.output,
                    self.progress.emit,
                )
                self.progress.emit("下载与解压完成，正在按已保存参数自动排版…")
                result = self._process_batches()
                result["type"] = "downloaded_and_processed"
                result["files"] = files
                self.completed.emit(result)
            elif self.action == "process":
                self.completed.emit(self._process_batches())
            else:
                raise RuntimeError(f"未知操作：{self.action}")
        except Exception as error:
            self.failed.emit(str(error))

    def _process_batches(self) -> dict:
        if self.output is None or self.settings is None:
            raise RuntimeError("缺少排版位置或排版设置。")
        platform_root = self.output / self.platform_name
        batch_folders = sorted(
            folder
            for folder in platform_root.rglob("*")
            if folder.is_dir()
            and len(folder.name) == 12
            and folder.name.isdigit()
            and not {"PROCESSED", "TEST_SAMPLE"}.intersection(
                folder.parts
            )
            and discover_images(folder)
        )
        if self.batch_numbers:
            selected = set(self.batch_numbers)
            batch_folders = [
                folder for folder in batch_folders if folder.name in selected
            ]
        if not batch_folders:
            raise RuntimeError(
                f"没有找到 {self.platform_name} 已解压的生产批次文件夹。"
            )
        if self.sample_limit:
            batch_folders = batch_folders[:1]
        completed = []
        for index, folder in enumerate(batch_folders, start=1):
            images = discover_images(folder)
            if self.sample_limit:
                images = images[: self.sample_limit]
                output_name = "TEST_SAMPLE"
            else:
                output_name = "PROCESSED"
            destination = (
                platform_root / output_name / folder.name
            )
            self.progress.emit(
                f"[{index}/{len(batch_folders)}] {folder.name}："
                f"正在排版 {len(images)} 张图片"
            )
            result = generate_layout(
                images,
                destination,
                self.settings,
                lambda stage, current, total, name: self.progress.emit(
                    f"{folder.name} · {stage} {current}/{total}"
                )
                if current == total or current % 50 == 0
                else None,
            )
            completed.append((folder.name, result))
        return {
            "type": "processed",
            "platform": self.platform_name,
            "batches": completed,
            "test": bool(self.sample_limit),
            "output_folder": str(platform_root / output_name),
        }


class AutomationDialog(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ERP 生产批次中心")
        self.resize(940, 640)
        self.thread: QThread | None = None
        self.worker: AutomationWorker | None = None
        self.records: list[BatchRecord] = []
        self.preferences = QSettings("AutomaticPrint", "AutomaticPrint")

        self.platform = QComboBox()
        for name in ERP_PLATFORMS:
            self.platform.addItem(name, name)
        self.platform.setCurrentText("隆丰")

        default_root = (
            Path(
                QStandardPaths.writableLocation(
                    QStandardPaths.DesktopLocation
                )
            )
            / "AutomaticPrintDownloads"
        )
        self.output = QLineEdit(
            self.preferences.value(
                "automation/output_location", str(default_root), str
            )
        )
        browse = QPushButton("选择…")
        browse.clicked.connect(self.choose_output)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output)
        output_row.addWidget(browse)

        self.summary = QLabel("尚未读取隆丰已生成批次。")
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["选择", "批次号", "项目", "件数", "类型", "创建时间", "生产图"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)

        self.refresh_button = QPushButton("刷新批次")
        self.refresh_button.clicked.connect(self.refresh_current_section)
        self.select_button = QPushButton("全选可下载批次")
        self.select_button.clicked.connect(self.select_all_ready)
        self.download_button = QPushButton("一键下载并自动排版")
        self.download_button.clicked.connect(self.download_selected)
        self.process_button = QPushButton("重新排版已下载批次")
        self.process_button.clicked.connect(self.process_batches)
        self.settings_button = QPushButton("打印参数设置…")
        self.settings_button.clicked.connect(self.open_settings)
        self.test_mode = QCheckBox(
            "快速测试模式：只处理第一个批次的前 5 张"
        )
        self.test_mode.setChecked(True)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)

        actions = QHBoxLayout()
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.select_button)
        actions.addWidget(self.download_button)
        actions.addWidget(self.process_button)
        actions.addWidget(self.settings_button)

        generation_page = QWidget()
        generation_layout = QVBoxLayout(generation_page)
        generation_intro = QLabel(
            "从已接单、尚未进入生产中的订单生成生产批次。"
            "程序会读取并显示 CBT / 非 CBT 数量；最终确认后才生成，"
            "批次生成后无法撤销。"
        )
        generation_intro.setWordWrap(True)
        self.generation_table = QTableWidget(0, 5)
        self.generation_table.setHorizontalHeaderLabels(
            ["物流分类", "项目", "件数", "订单组成", "操作状态"]
        )
        self.generation_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        generation_warning = QLabel(
            "安全保护：生成前会显示平台、CBT / 非 CBT 数量，"
            "并要求最终确认。"
        )
        generation_warning.setWordWrap(True)
        generation_layout.addWidget(generation_intro)
        generation_layout.addWidget(self.generation_table)
        generation_layout.addWidget(generation_warning)

        management_page = QWidget()
        management_layout = QVBoxLayout(management_page)
        management_intro = QLabel(
            "查看已生成的生产批次。勾选批次后，程序会一键下载、"
            "解压并按已保存参数自动排版。"
        )
        management_intro.setWordWrap(True)
        management_layout.addWidget(management_intro)
        management_layout.addWidget(QLabel("下载保存位置"))
        management_layout.addLayout(output_row)
        management_layout.addWidget(self.summary)
        management_layout.addWidget(self.table)
        management_layout.addWidget(self.test_mode)
        management_layout.addLayout(actions)
        management_layout.addWidget(self.log)

        production_page = QWidget()
        production_layout = QVBoxLayout(production_page)
        production_title = QLabel(
            "批次管理：查看已经生成且正在生产的批次，并下载生产图。"
        )
        production_title.setWordWrap(True)
        production_layout.addWidget(production_title)
        production_layout.addWidget(management_page)

        accepted_page = QWidget()
        accepted_layout = QVBoxLayout(accepted_page)
        accepted_intro = QLabel(
            "显示该 ERP 平台已经接单、但尚未进入生产中的订单。"
            "批次生成功能只在这个区域；生成成功后，批次进入“生产中”。"
        )
        accepted_intro.setWordWrap(True)
        self.accepted_summary = QLabel(
            f"{self.platform.currentText()}：尚未读取待生产订单数量。"
        )
        self.accepted_summary.setTextFormat(Qt.RichText)
        self.accepted_table = QTableWidget(0, 6)
        self.accepted_table.setHorizontalHeaderLabels(
            ["订单号", "物流", "项目", "件数", "接单时间", "操作"]
        )
        self.accepted_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        accepted_layout.addWidget(accepted_intro)
        accepted_layout.addWidget(self.accepted_summary)
        accepted_layout.addWidget(self.accepted_table)
        accepted_layout.addWidget(QLabel("批次生成"))
        accepted_layout.addWidget(generation_page)

        cleared_page = QWidget()
        cleared_layout = QVBoxLayout(cleared_page)
        cleared_intro = QLabel(
            "该平台所有生产项目均已完成的订单会显示在这里。"
        )
        cleared_intro.setWordWrap(True)
        self.cleared_summary = QLabel(
            f"{self.platform.currentText()}：尚未读取生产中数量。"
        )
        self.cleared_table = QTableWidget(0, 6)
        self.cleared_table.setHorizontalHeaderLabels(
            ["订单号", "物流", "项目", "件数", "完成时间", "状态"]
        )
        self.cleared_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        cleared_layout.addWidget(cleared_intro)
        cleared_layout.addWidget(self.cleared_summary)
        cleared_layout.addWidget(self.cleared_table)

        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(accepted_page, "已接单")
        self.main_tabs.addTab(production_page, "生产中")
        self.main_tabs.addTab(cleared_page, "已清单")
        self.main_tabs.setCurrentIndex(0)
        self.main_tabs.currentChanged.connect(self.main_tab_changed)
        self.platform.currentTextChanged.connect(self.platform_changed)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("ERP 平台"))
        layout.addWidget(self.platform)
        layout.addWidget(self.main_tabs)

    def choose_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "选择生产图保存位置", self.output.text()
        )
        if folder:
            self.output.setText(folder)
            self.preferences.setValue("automation/output_location", folder)

    def platform_changed(self, name: str) -> None:
        self.records = []
        self.table.setRowCount(0)
        self.select_button.setText("全选可下载批次")
        self.summary.setText(f"尚未读取 {name} 已生成批次。")
        self.accepted_table.setRowCount(0)
        self.accepted_summary.setText(
            f"{name}：尚未读取待生产订单数量。"
        )
        self.cleared_table.setRowCount(0)
        self.cleared_summary.setText(f"{name}：尚未读取生产中数量。")
        self.refresh_current_section()

    def main_tab_changed(self, index: int) -> None:
        self.refresh_current_section()

    def refresh_current_section(self) -> None:
        if self.thread is not None:
            return
        action = (
            "status_and_list"
            if self.main_tabs.currentIndex() == 1
            else "status"
        )
        self.log.clear()
        self._start_worker(
            AutomationWorker(action, self.platform.currentData())
        )

    @Slot(object)
    def status_finished(self, status) -> None:
        name = self.platform.currentText()
        if status.accepted_count:
            self.accepted_summary.setText(
                f"{name}：<span style='color:#c62828; font-size:16px; "
                f"font-weight:700;'>{status.accepted_count} 个</span>"
                "已接单订单尚未进入生产中。"
            )
        else:
            self.accepted_summary.setText(
                f"{name}：<span style='color:#2e7d32; font-size:16px; "
                "font-weight:700;'>0 个</span>"
                "已接单订单尚未进入生产中。"
            )
        self.cleared_table.setRowCount(0)
        if status.cleared:
            self.cleared_summary.setText(
                f"{name}：生产中为 0，平台已清单。"
            )
            self.cleared_table.setRowCount(1)
            values = [name, "—", "—", "0", "—", "已清单"]
            for column, value in enumerate(values):
                self.cleared_table.setItem(
                    0, column, QTableWidgetItem(value)
                )
        else:
            self.cleared_summary.setText(
                f"{name}：生产中还有 {status.production_count} 个，"
                "尚未达到已清单条件。"
            )

    def refresh_batches(self) -> None:
        if self.thread is not None:
            return
        self.log.clear()
        self._start_worker(
            AutomationWorker("list", self.platform.currentData())
        )

    @Slot(object)
    def batches_finished(self, records: list[BatchRecord]) -> None:
        self.records = records
        self.table.setRowCount(len(records))
        self.select_button.setText("全选可下载批次")
        ready_count = 0
        for row, record in enumerate(records):
            checkbox = QCheckBox()
            checkbox.setEnabled(record.production_images_ready)
            self.table.setCellWidget(row, 0, checkbox)
            values = [
                record.batch_number,
                str(record.item_count),
                str(record.piece_count),
                record.batch_type,
                record.created_at,
                "可下载" if record.production_images_ready else "生成中",
            ]
            for column, value in enumerate(values, start=1):
                self.table.setItem(row, column, QTableWidgetItem(value))
            ready_count += int(record.production_images_ready)
        self.summary.setText(
            f"{self.platform.currentText()}：显示 {len(records)} 个最新批次，"
            f"{ready_count} 个生产图可下载。"
        )

    def select_all_ready(self) -> None:
        ready_checkboxes = [
            self.table.cellWidget(row, 0)
            for row in range(self.table.rowCount())
            if self.table.cellWidget(row, 0)
            and self.table.cellWidget(row, 0).isEnabled()
        ]
        if not ready_checkboxes:
            return
        select_all = not (
            all(checkbox.isChecked() for checkbox in ready_checkboxes)
        )
        for checkbox in ready_checkboxes:
            checkbox.setChecked(select_all)
        self.select_button.setText(
            "取消全选" if select_all else "全选可下载批次"
        )

    def download_selected(self) -> None:
        selected = [
            self.table.item(row, 1).text()
            for row in range(self.table.rowCount())
            if self.table.cellWidget(row, 0)
            and self.table.cellWidget(row, 0).isChecked()
        ]
        if not selected:
            QMessageBox.warning(
                self, "请选择批次", "请至少选择一个生产图可下载的批次。"
            )
            return
        self.preferences.setValue(
            "automation/output_location", self.output.text().strip()
        )
        self._start_worker(
            AutomationWorker(
                "download",
                self.platform.currentData(),
                output=Path(self.output.text().strip()),
                batch_numbers=selected,
                settings=self._current_layout_settings(),
                sample_limit=5 if self.test_mode.isChecked() else None,
            )
        )

    def open_settings(self) -> None:
        window = self.window()
        if hasattr(window, "open_settings_dialog"):
            window.open_settings_dialog()

    def process_batches(self) -> None:
        output = Path(self.output.text().strip())
        if not output.is_dir():
            QMessageBox.warning(
                self, "找不到文件夹", "请选择包含已下载生产图的文件夹。"
            )
            return
        self._start_worker(
            AutomationWorker(
                "process",
                self.platform.currentData(),
                output=output,
                settings=self._current_layout_settings(),
                sample_limit=5 if self.test_mode.isChecked() else None,
            )
        )

    def _current_layout_settings(self) -> LayoutSettings:
        window = self.window()
        if window is None or not hasattr(window, "width"):
            return LayoutSettings(png_engine="libvips")
        return LayoutSettings(
            media_width_mm=window.width.value(),
            spacing_mm=window.spacing.value(),
            margin_mm=window.margin.value(),
            dpi=window.dpi.value(),
            png_compression_level=window.png_compression.currentData(),
            png_engine=window.png_engine.currentData(),
            worker_threads=window.worker_threads.value(),
            number_images=window.number_images.isChecked(),
            number_gap_mm=window.label_settings.gap.value(),
            number_font_size_mm=window.label_settings.font_size.value(),
            label_text_template=window.label_settings.text_template.text(),
            label_position=window.label_settings.position.currentData(),
            label_offset_x_mm=window.label_settings.offset_x.value(),
            label_offset_y_mm=window.label_settings.offset_y.value(),
            label_date_format=(
                window.label_settings.date_format.text().strip()
                or "%Y-%m-%d"
            ),
        )

    def _start_worker(self, worker: AutomationWorker) -> None:
        if self.thread is not None:
            return
        self._set_actions_enabled(False)
        self.thread = QThread(self)
        self.worker = worker
        worker.moveToThread(self.thread)
        self.thread.started.connect(worker.run)
        worker.progress.connect(self.log.appendPlainText)
        worker.batches_loaded.connect(self.batches_finished)
        worker.status_loaded.connect(self.status_finished)
        worker.completed.connect(self.action_finished)
        worker.failed.connect(self.failed)
        worker.batches_loaded.connect(self.thread.quit)
        worker.completed.connect(self.thread.quit)
        worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.clear_worker)
        if worker.action == "status":
            worker.status_loaded.connect(self.thread.quit)
        self.thread.start()

    @Slot(object)
    def action_finished(self, result: dict) -> None:
        if result["type"] == "downloaded_and_processed":
            mode = "测试小样" if result["test"] else "生产批次"
            self.summary.setText(
                f"{result['platform']}：已下载并解压 "
                f"{len(result['files'])} 个文件，已完成 "
                f"{len(result['batches'])} 个{mode}排版。"
            )
            QMessageBox.information(self, "自动处理完成", self.summary.text())
        else:
            mode = "测试小样" if result["test"] else "生产批次"
            self.summary.setText(
                f"{result['platform']}：已生成 "
                f"{len(result['batches'])} 个{mode} PNG。"
            )
            QMessageBox.information(self, "排版完成", self.summary.text())
        output_folder = Path(result["output_folder"])
        if output_folder.is_dir():
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(output_folder.resolve()))
            )

    @Slot(str)
    def failed(self, message: str) -> None:
        self.log.appendPlainText(f"停止：{message}")
        QMessageBox.critical(self, "操作已停止", message)

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.platform.setEnabled(enabled)
        self.main_tabs.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)
        self.select_button.setEnabled(enabled)
        self.download_button.setEnabled(enabled)
        self.process_button.setEnabled(enabled)
        self.settings_button.setEnabled(enabled)

    @Slot()
    def clear_worker(self) -> None:
        self.thread = None
        self.worker = None
        self._set_actions_enabled(True)

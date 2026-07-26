from pathlib import Path

from PySide6.QtCore import (
    QSettings,
    QStandardPaths,
    Qt,
)
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..automation.platforms import ERP_PLATFORMS
from ..layout import LayoutSettings
from ..ui.worker_bridge import BatchWorkerBridge
from .batch_actions import BatchActionsMixin
from .generation_actions import GenerationActionsMixin
from .local_actions import LocalActionsMixin
from .local_page import build_local_page
from .pages import (
    build_accepted_page,
    build_production_page,
)
from .thread_actions import ThreadActionsMixin
from .worker import AutomationWorker


class AutomationDialog(
    GenerationActionsMixin,
    LocalActionsMixin,
    BatchActionsMixin,
    ThreadActionsMixin,
    QWidget,
):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("生产批次中心")
        self.resize(940, 640)
        self.thread = None
        self.worker = None
        self.worker_bridge = BatchWorkerBridge(self)
        self.records = []
        self.pending_batch_plan = None
        self.preferences = QSettings("AutomaticPrint", "AutomaticPrint")
        self._connect_worker_bridge()
        self._build_controls()
        self._build_tabs()
        self._build_layout()
        self.platform.currentTextChanged.connect(self.platform_changed)
        self.main_tabs.currentChanged.connect(self.main_tab_changed)
        self.show_platform_batch_rules(self.platform.currentData())

    def _connect_worker_bridge(self) -> None:
        bridge = self.worker_bridge
        bridge.progress.connect(self.append_log)
        bridge.progress.connect(self.show_progress_message)
        bridge.batches_loaded.connect(self.batches_finished)
        bridge.status_loaded.connect(self.status_finished)
        bridge.plan_loaded.connect(self.generation_plan_finished)
        bridge.completed.connect(self.action_finished)
        bridge.failed.connect(self.failed)

    def _build_controls(self) -> None:
        self.platform = QComboBox()
        for name in ERP_PLATFORMS:
            self.platform.addItem(name, name)
        self.platform.setCurrentText("Haloo")
        default = (
            Path(
                QStandardPaths.writableLocation(
                    QStandardPaths.DesktopLocation
                )
            )
            / "AutomaticPrintDownloads"
        )
        self.output = QLineEdit(
            self.preferences.value(
                "automation/output_location", str(default), str
            )
        )
        browse = QPushButton("选择…")
        browse.clicked.connect(self.choose_output)
        self.output_row = QHBoxLayout()
        self.output_row.addWidget(self.output)
        self.output_row.addWidget(browse)
        self.settings_button = QPushButton("打印参数设置…")
        self.settings_button.clicked.connect(self.open_settings)
        self.loading_panel = QWidget()
        self.loading_panel.setStyleSheet(
            "QWidget{background:#e8f1ff;border:1px solid #6f9ee8;"
            "border-radius:6px;} QLabel{border:none;color:#173f73;"
            "font-size:14px;font-weight:700;}"
        )
        loading = QVBoxLayout(self.loading_panel)
        self.loading_label = QLabel("正在准备…")
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setTextVisible(False)
        loading.addWidget(self.loading_label)
        loading.addWidget(self.loading_bar)
        self.loading_panel.hide()

    def _build_tabs(self) -> None:
        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(build_accepted_page(self), "已接单")
        self.main_tabs.addTab(
            build_production_page(self, self.output_row), "生产批次"
        )
        self.main_tabs.addTab(build_local_page(self), "本地文件")

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("生产平台"))
        layout.addWidget(self.platform)
        layout.addWidget(self.loading_panel)
        layout.addWidget(self.main_tabs)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(self.settings_button)
        layout.addLayout(footer)
        for label in self.findChildren(QLabel):
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)

    def platform_changed(self, name: str) -> None:
        self.pending_batch_plan = None
        self.generate_rules_button.setEnabled(False)
        self.records = []
        self.table.setRowCount(0)
        self.summary.setText(f"尚未读取 {name} 已生成批次。")
        self.accepted_table.setRowCount(0)
        self.accepted_summary.setText(
            f"{name}：尚未读取待生产订单数量。"
        )
        self.show_platform_batch_rules(name)
        self.refresh_current_section()

    def main_tab_changed(self, _index: int) -> None:
        self.refresh_current_section()

    def refresh_current_section(self) -> None:
        if self.thread is not None:
            return
        if self.main_tabs.currentIndex() == 2:
            self.refresh_local_batches()
            return
        if self.main_tabs.currentIndex() == 1:
            self.show_cached_batches()
            return
        self.log.clear()
        self._start_worker(
            AutomationWorker("status", self.platform.currentData())
        )

    def refresh_batches(self) -> None:
        self._start_worker(
            AutomationWorker("list", self.platform.currentData())
        )

    def _current_layout_settings(self) -> LayoutSettings:
        window = self.window()
        if window is None or not hasattr(window, "width"):
            return LayoutSettings(png_engine="libvips")
        label = window.label_settings
        return LayoutSettings(
            media_width_mm=window.width.value(),
            spacing_mm=window.spacing.value(),
            margin_mm=window.margin.value(),
            dpi=window.dpi.value(),
            png_compression_level=window.png_compression.currentData(),
            png_engine=window.png_engine.currentData(),
            worker_threads=window.worker_threads.value(),
            allow_rotation=window.allow_rotation.isChecked(),
            rotation_direction=window.rotation_direction.currentData(),
            number_images=window.number_images.isChecked(),
            number_gap_mm=label.gap.value(),
            number_font_size_mm=label.font_size.value(),
            label_text_template=label.text_template.text(),
            label_position=label.position.currentData(),
            label_offset_x_mm=label.offset_x.value(),
            label_offset_y_mm=label.offset_y.value(),
            label_date_format=label.date_format.text().strip() or "%Y-%m-%d",
        )

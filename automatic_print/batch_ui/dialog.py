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
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..automation.platforms import ERP_PLATFORMS
from ..layout import LayoutSettings
from ..ui.worker_bridge import BatchWorkerBridge
from ..ui.layout_values import settings_from_window
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
        self.local_only = True
        self.setWindowTitle("本地排版工作台")
        self.resize(940, 640)
        self.thread = None
        self.worker = None
        self.worker_bridge = BatchWorkerBridge(self)
        self.records = []
        self.pending_batch_plan = None
        self.preferences = (
            parent.preferences if parent is not None and hasattr(parent, "preferences")
            else QSettings("AutomaticPrint", "AutomaticPrint")
        )
        self._connect_worker_bridge()
        self._build_controls()
        self._build_tabs()
        self._build_layout()
        self.platform.currentTextChanged.connect(self.platform_changed)
        self.main_tabs.currentChanged.connect(self.main_tab_changed)
        self.show_platform_batch_rules(self.platform.currentData())
        self.refresh_current_section()

    def _connect_worker_bridge(self) -> None:
        bridge = self.worker_bridge
        bridge.progress.connect(self.append_log)
        bridge.progress.connect(self.show_progress_message)
        bridge.batches_loaded.connect(self.batches_finished)
        bridge.status_loaded.connect(self.status_finished)
        bridge.plan_loaded.connect(self.generation_plan_finished)
        bridge.completed.connect(self.action_finished)
        bridge.failed.connect(self.failed)
        bridge.cancelled.connect(self.task_cancelled)

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
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(100)
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
        self.stop_button = QPushButton("停止当前处理")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_current_task)
        loading.addWidget(self.loading_label)
        loading.addWidget(self.loading_bar)
        loading.addWidget(self.stop_button)
        self.loading_panel.hide()

    def _build_tabs(self) -> None:
        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(build_local_page(self), "本地排版")
        self.main_tabs.addTab(build_accepted_page(self), "已接单")
        self.main_tabs.addTab(
            build_production_page(self, self.output_row), "生产批次"
        )
        if self.local_only:
            self.main_tabs.setTabVisible(1, False)
            self.main_tabs.setTabVisible(2, False)
            self.main_tabs.tabBar().hide()

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        if not self.local_only:
            layout.addWidget(QLabel("生产平台"))
            layout.addWidget(self.platform)
        layout.addWidget(self.loading_panel)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.main_tabs)
        layout.addWidget(scroll)
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
        if self.local_only:
            return
        if self.thread is not None:
            return
        if self.main_tabs.currentIndex() == 0:
            self.refresh_local_batches()
            return
        if self.main_tabs.currentIndex() == 2:
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
        return settings_from_window(window)

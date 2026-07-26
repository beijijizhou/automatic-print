from __future__ import annotations

from PySide6.QtCore import QSettings, QStandardPaths, QThread, QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..automation_dialog import AutomationDialog
from ..layout import png_engine_name
from .generation_actions import GenerationActionsMixin
from .label_settings import LabelSettingsDialog
from .preferences import PreferencesMixin
from .update_actions import UpdateActionsMixin
from .worker_bridge import MainWindowWorkerBridge


class MainWindow(
    PreferencesMixin,
    GenerationActionsMixin,
    UpdateActionsMixin,
    QMainWindow,
):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("生产批次中心")
        self.resize(980, 700)
        self.thread: QThread | None = None
        self.worker = None
        self.worker_bridge = MainWindowWorkerBridge(self)
        self.update_thread: QThread | None = None
        self.update_worker = None
        self.update_is_silent = True
        self.started_at = None
        self.stage_started_at = None
        self.current_stage = ""
        self.current_count = 0
        self.current_total = 0
        self.active_png_compression = 1
        self.active_png_engine = "pillow"
        self.preferences = QSettings("AutomaticPrint", "AutomaticPrint")
        self._connect_worker_bridge()
        self.clock = QTimer(self)
        self.clock.setInterval(1000)
        self.clock.timeout.connect(self.refresh_timing)
        self._build_settings()
        self._build_home()
        for label in self.findChildren(QLabel):
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        QTimer.singleShot(2500, lambda: self.check_for_updates(True))

    def _connect_worker_bridge(self) -> None:
        bridge = self.worker_bridge
        bridge.layout_progress.connect(self.update_progress)
        bridge.layout_finished.connect(self.generation_finished)
        bridge.layout_failed.connect(self.generation_failed)
        bridge.update_finished.connect(self.update_check_finished)
        bridge.update_failed.connect(self.update_check_failed)

    def _build_settings(self) -> None:
        self.folder = QLineEdit(
            self.preferences.value("source_location", "", str)
        )
        browse = QPushButton("选择图片文件夹…")
        browse.clicked.connect(self.choose_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder)
        folder_row.addWidget(browse)
        self.width = self._box(580, 50, 5000)
        self.spacing = self._box(8, 0, 100)
        self.margin = self._box(3, 0, 100)
        self.dpi = QSpinBox()
        self.dpi.setRange(72, 1200)
        self.worker_threads = QSpinBox()
        self.worker_threads.setRange(1, 32)
        self.label_settings = LabelSettingsDialog(self)
        self.number_images = self.label_settings.enabled
        label_button = QPushButton("打开标签与文字设置…")
        label_button.clicked.connect(self.label_settings.exec)
        self.png_compression = QComboBox()
        self.png_compression.addItem("等级 1 — 轻度压缩（推荐）", 1)
        self.png_compression.addItem("等级 0 — 不压缩（文件最大）", 0)
        self.png_compression.addItem("等级 3 — 中度压缩（文件更小）", 3)
        self.png_engine = QComboBox()
        self.png_engine.addItem("标准快速模式（推荐）", "pillow")
        if png_engine_name() == "大图节省内存模式":
            self.png_engine.addItem("大图节省内存模式", "libvips")
        self.load_layout_preferences()
        form = QFormLayout()
        for label, widget in (
            ("图片文件夹", folder_row),
            ("材料宽度（毫米）", self.width),
            ("图片间距（毫米）", self.spacing),
            ("外边距（毫米）", self.margin),
            ("输出分辨率", self.dpi),
            ("并行处理线程数", self.worker_threads),
            ("标签与文字", label_button),
            ("图片保存方式", self.png_engine),
            ("图片压缩", self.png_compression),
        ):
            form.addRow(label, widget)
        default = QStandardPaths.writableLocation(
            QStandardPaths.DesktopLocation
        )
        self.output_location = QLineEdit(
            self.preferences.value("output_location", default, str)
        )
        output_button = QPushButton("选择保存位置…")
        output_button.clicked.connect(self.choose_output_location)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_location)
        output_row.addWidget(output_button)
        form.addRow("任务保存位置", output_row)
        self.job_path = QLineEdit()
        self.job_path.setReadOnly(True)
        form.addRow("本次任务文件夹", self.job_path)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFormat("尚未开始")
        self.status = QLabel("请选择包含图片的文件夹。")
        self.current_file = QLabel("当前文件：—")
        self.run_log = QPlainTextEdit()
        self.run_log.setReadOnly(True)
        self.run_log.setMaximumHeight(115)
        self.generate_button = QPushButton("高级：手动生成单张排版图片")
        self.generate_button.clicked.connect(self.generate)
        save_button = QPushButton("保存参数")
        save_button.clicked.connect(self.save_layout_preferences)
        body = QVBoxLayout()
        body.addLayout(form)
        body.addStretch()
        for widget in (
            self.progress,
            self.status,
            self.current_file,
            self.run_log,
            self.generate_button,
            save_button,
        ):
            body.addWidget(widget)
        container = QWidget()
        container.setLayout(body)
        self.settings_dialog = QDialog(self)
        self.settings_dialog.setWindowTitle("自动排版参数设置")
        self.settings_dialog.resize(760, 650)
        QVBoxLayout(self.settings_dialog).addWidget(container)

    def _build_home(self) -> None:
        self.automation_home = AutomationDialog(self)
        self.version_label = QLabel(f"版本 {__version__}")
        self.check_update_button = QPushButton("检查更新")
        self.check_update_button.clicked.connect(
            lambda: self.check_for_updates(False)
        )
        footer = QHBoxLayout()
        footer.addWidget(self.version_label)
        footer.addStretch()
        footer.addWidget(self.check_update_button)
        layout = QVBoxLayout()
        layout.addWidget(self.automation_home)
        layout.addLayout(footer)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def has_active_tasks(self) -> bool:
        return any(
            (
                self.thread is not None,
                self.update_thread is not None,
                self.automation_home.thread is not None,
            )
        )

    def closeEvent(self, event) -> None:
        if self.has_active_tasks():
            event.ignore()
            self.automation_home.loading_label.setText(
                "任务仍在运行，完成后程序会安全关闭。"
            )
            self.automation_home.loading_panel.show()
            return
        event.accept()

    @staticmethod
    def _box(value, minimum, maximum) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setDecimals(1)
        box.setValue(value)
        return box

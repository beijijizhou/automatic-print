from __future__ import annotations

from PySide6.QtCore import QSettings, QStandardPaths, QThread, QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
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
    QScrollArea,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, __version_display__
from ..branding import application_icon
from .segmented_output import SegmentedOutputSettings
from ..automation_dialog import AutomationDialog
from ..layout import png_engine_name
from .generation_actions import GenerationActionsMixin
from .color_block_settings import ColorBlockSettingsDialog
from .cutter_settings import CutterSettingsPanel
from .label_settings import LabelSettingsDialog
from .preferences import PreferencesMixin
from .preference_autosave import PreferenceAutosave
from .generation_preview import GenerationPreviewController
from .update_actions import UpdateActionsMixin
from .worker_bridge import MainWindowWorkerBridge


class MainWindow(
    PreferencesMixin,
    GenerationActionsMixin,
    UpdateActionsMixin,
    QMainWindow,
):
    def __init__(self, preferences=None) -> None:
        super().__init__()
        self.setWindowTitle("本地排版工作台")
        self.setWindowIcon(application_icon())
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
        self.preferences = preferences if preferences is not None else QSettings("AutomaticPrint", "AutomaticPrint")
        self._connect_worker_bridge()
        self.clock = QTimer(self)
        self.clock.setInterval(1000)
        self.clock.timeout.connect(self.refresh_timing)
        self._build_settings()
        self._build_home()
        from .workbench_style import apply_workbench_style
        apply_workbench_style(self)
        self.preference_autosave = PreferenceAutosave(self)
        self.generation_preview = GenerationPreviewController(self)
        for label in self.findChildren(QLabel):
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.startup_update_timer = QTimer(self)
        self.startup_update_timer.setSingleShot(True)
        self.startup_update_timer.timeout.connect(lambda: self.check_for_updates(True) if self.isVisible() else None)
        self.startup_update_timer.start(2500)

    def _connect_worker_bridge(self) -> None:
        bridge = self.worker_bridge
        bridge.layout_progress.connect(self.update_progress)
        bridge.layout_finished.connect(self.generation_finished)
        bridge.layout_failed.connect(self.generation_failed)
        bridge.layout_cancelled.connect(self.generation_cancelled)
        bridge.update_finished.connect(self.update_check_finished)
        bridge.update_failed.connect(self.update_check_failed)
        bridge.update_progress.connect(self.show_update_progress)
    def _build_settings(self) -> None:
        self.folder = QLineEdit(
            self.preferences.value("source_location", "", str)
        )
        browse = QPushButton("选择图片文件夹…")
        browse.clicked.connect(self.choose_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder)
        folder_row.addWidget(browse)
        self.width = self._box(600, 50, 5000)
        self.spacing = self._box(8, 0, 100)
        self.margin = self._box(3, 0, 100)
        self.margin.setToolTip(
            "只在整张批次排版图的开头和结尾保留空间，不影响图片之间的距离。"
        )
        self.dpi = QSpinBox()
        self.dpi.setRange(72, 1200)
        from .output_dpi import build_output_dpi
        self.output_dpi_control = build_output_dpi(self)
        from .header_gap import build_header_gap
        build_header_gap(self)
        self.worker_threads = QSpinBox()
        self.worker_threads.setRange(1, 32)
        self.segmented_output = SegmentedOutputSettings(self.preferences, self)
        self.allow_rotation = QCheckBox("允许旋转以节省材料")
        self.allow_rotation.setChecked(True)
        self.rotation_direction = QComboBox()
        self.rotation_direction.addItem("向左旋转（默认）", "left")
        self.rotation_direction.addItem("向右旋转", "right")
        self.label_settings = LabelSettingsDialog(self)
        self.number_images = self.label_settings.enabled
        label_button = QPushButton("打开标签与文字设置…")
        label_button.clicked.connect(self.label_settings.exec)
        self.color_block_settings = ColorBlockSettingsDialog(self)
        color_block_button = QPushButton("打开色块设置…")
        color_block_button.clicked.connect(self.color_block_settings.exec)
        self.png_compression = QComboBox()
        self.png_compression.addItem("等级 1 — 轻度压缩（推荐）", 1)
        self.png_compression.addItem("等级 0 — 不压缩（文件最大）", 0)
        self.png_compression.addItem("等级 3 — 中度压缩（文件更小）", 3)
        self.png_engine = QComboBox()
        self.png_engine.addItem("标准快速模式（推荐）", "pillow")
        if png_engine_name() == "大图节省内存模式":
            self.png_engine.addItem("大图节省内存模式", "libvips")
        self.load_layout_preferences()
        self.cutter_settings = CutterSettingsPanel(
            self.preferences, self.width, self.allow_rotation,
            self.rotation_direction, self, block=self.color_block_settings,
        )
        form = QFormLayout()
        for label, widget in (
            ("图片文件夹", folder_row),
            ("膜与切膜规则", self.cutter_settings),
            ("上下垂直间距（毫米）", self.spacing),
            ("膜标签与图案最小间距", self.membrane_gap),
            ("批次开头与结尾留白（毫米）", self.margin),
            ("输出分辨率", self.output_dpi_control),
            ("并行处理线程数", self.worker_threads),
            ("图片旋转", self.allow_rotation),
            ("旋转方向", self.rotation_direction),
            ("标签与文字", label_button),
            ("剪膜机色块", color_block_button),
            ("图片保存方式", self.png_engine),
            ("图片压缩", self.png_compression),
            ("分段与并行保存", self.segmented_output),
        ):
            form.addRow(label, widget)
        from .spacing_settings import bind_spacing_description
        bind_spacing_description(form, self)
        default = QStandardPaths.writableLocation(QStandardPaths.DesktopLocation)
        from .output_location import build_output_location
        output_row = build_output_location(self, default)
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
        preview_button = QPushButton("仅预览整批（不生成文件）")
        preview_button.clicked.connect(lambda: self.generate(preview_only=True))
        self.generate_button = QPushButton("生成最终打印文件")
        self.generate_button.clicked.connect(self.generate)
        self.stop_generation_button = QPushButton("停止当前排版")
        self.stop_generation_button.setEnabled(False)
        self.stop_generation_button.clicked.connect(self.stop_generation)
        save_button = QPushButton("保存参数")
        save_button.clicked.connect(self.save_layout_preferences)
        body = QVBoxLayout()
        from .print_settings_navigation import build_settings_navigation
        body.addWidget(build_settings_navigation(self, form))
        body.addStretch()
        for widget in (
            self.progress,
            self.status,
            self.current_file,
            self.run_log,
            preview_button,
            self.generate_button,
            self.stop_generation_button,
            save_button,
        ):
            body.addWidget(widget)
        container = QWidget()
        body.addWidget(self.build_reset_button())
        container.setLayout(body)
        self.settings_dialog = QDialog(self)
        self.settings_dialog.setWindowTitle("自动排版参数设置")
        self.settings_dialog.resize(760, 650)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        QVBoxLayout(self.settings_dialog).addWidget(scroll)

    def _build_home(self) -> None:
        self.automation_home = AutomationDialog(self)
        self.version_label = QLabel(f"版本 {__version_display__}")
        self.version_label.setToolTip(f"内部版本：{__version__}")
        self.check_update_button = QPushButton("检查更新")
        self.check_update_button.clicked.connect(
            lambda: self.check_for_updates(False)
        )
        footer = QHBoxLayout()
        footer.addWidget(self.version_label)
        footer.addStretch()
        settings_button = self.automation_home.settings_button
        settings_button.setMinimumHeight(36)
        footer.addWidget(settings_button)
        footer.addWidget(self.check_update_button)
        from .developer_mode import build_developer_mode
        build_developer_mode(self, footer)
        layout = QVBoxLayout()
        layout.addWidget(self.build_update_status())
        layout.addWidget(self.automation_home)
        layout.addLayout(footer)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
    def has_active_tasks(self) -> bool:
        from .developer_mode import developer_task_active
        return any((self.thread is not None, self.update_thread is not None,
                    self.automation_home.thread is not None, developer_task_active(self),
                    getattr(getattr(self, 'bulk_controller', None), 'thread', None) is not None))

    def closeEvent(self, event) -> None:
        from .immediate_exit import exit_now
        exit_now(self)
        event.accept()

    @staticmethod
    def _box(value, minimum, maximum) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(minimum, maximum)
        box.setDecimals(1)
        box.setValue(value)
        return box

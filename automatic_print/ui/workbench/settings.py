"""Build the canonical print-parameter dialog and its shared controls."""

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..color_block_settings import ColorBlockSettingsDialog
from ..cutter_settings import CutterSettingsPanel
from ..header_gap import build_header_gap
from ..label_settings import LabelSettingsDialog
from ..settings.output import (
    SegmentedOutputSettings,
    build_output_dpi,
    build_output_location,
    build_output_settings,
)
from ..print_settings_navigation import build_settings_navigation
from ..spacing_settings import bind_spacing_description
from ..spinbox_style import double_spinbox


def _build_parameter_controls(window) -> QFormLayout:
    from ..folder_dialog_paths import DEFAULT_DTF_SHARE
    window.folder = QLineEdit(
        window.preferences.value("source_location", "", str)
    )
    window.folder.setPlaceholderText(f"默认共享盘：{DEFAULT_DTF_SHARE}")
    browse = QPushButton("选择图片文件夹…")
    browse.clicked.connect(window.choose_folder)
    folder_row = QHBoxLayout()
    folder_row.addWidget(window.folder)
    folder_row.addWidget(browse)

    window.width = double_spinbox(600, 50, 5000)
    window.spacing = double_spinbox(8, 0, 100)
    window.margin = double_spinbox(3, 0, 100)
    window.margin.setToolTip(
        "只在整张批次排版图的开头和结尾保留空间，不影响图片之间的距离。"
    )
    window.dpi = QSpinBox()
    window.dpi.setRange(72, 1200)
    window.output_dpi_control = build_output_dpi(window)
    build_header_gap(window)
    window.worker_threads = QSpinBox()
    window.worker_threads.setRange(1, 32)
    window.worker_threads.setSpecialValueText('自动（最多4线程）')
    window.worker_threads.setToolTip(
        '设为自动时，单批次最多使用4线程；多个批次同时运行时按实际并行批次数均分。')
    window.segmented_output = SegmentedOutputSettings(window.preferences, window)
    window.allow_rotation = QCheckBox("允许旋转以节省材料")
    window.allow_rotation.setChecked(True)
    window.rotation_direction = QComboBox()
    window.rotation_direction.addItem("向左旋转（默认）", "left")
    window.rotation_direction.addItem("向右旋转", "right")

    window.label_settings = LabelSettingsDialog(window)
    window.number_images = window.label_settings.enabled
    label_button = QPushButton("打开标签与文字设置…")
    label_button.clicked.connect(window.label_settings.exec)
    window.color_block_settings = ColorBlockSettingsDialog(window)
    color_button = QPushButton("打开色块设置…")
    color_button.clicked.connect(window.color_block_settings.exec)
    build_output_settings(window)
    window.load_layout_preferences()
    window.cutter_settings = CutterSettingsPanel(
        window.preferences,
        window.width,
        window.allow_rotation,
        window.rotation_direction,
        window,
        block=window.color_block_settings,
    )

    form = QFormLayout()
    for label, widget in (
        ("图片文件夹", folder_row),
        ("膜与切膜规则", window.cutter_settings),
        ("上下垂直间距（毫米）", window.spacing),
        ("补足膜间距", window.membrane_gap_enabled),
        ("膜标签与图案最小间距", window.membrane_gap),
        ("超宽恢复", window.auto_fit_width),
        ("批次开头与结尾留白（毫米）", window.margin),
        ("输出分辨率", window.output_dpi_control),
        ("并行处理线程数", window.worker_threads),
        ("图片旋转", window.allow_rotation),
        ("旋转方向", window.rotation_direction),
        ("标签与文字", label_button),
        ("剪膜机色块", color_button),
        ("输出图片格式", window.output_format),
        ("图片保存方式", window.png_engine),
        ("图片压缩", window.png_compression),
        ("分段与并行保存", window.segmented_output),
    ):
        form.addRow(label, widget)
    bind_spacing_description(form, window)

    default = QStandardPaths.writableLocation(QStandardPaths.DesktopLocation)
    form.addRow("任务保存位置", build_output_location(window, default))
    window.job_path = QLineEdit()
    window.job_path.setReadOnly(True)
    form.addRow("切膜机文件位置", window.job_path)
    return form


def build_settings(window) -> None:
    form = _build_parameter_controls(window)
    window.save_settings_button = QPushButton("保存参数并返回排版")

    body = QVBoxLayout()
    body.setAlignment(Qt.AlignTop)
    tabs = build_settings_navigation(window, form)
    tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
    body.addWidget(tabs)
    actions = QHBoxLayout()
    actions.addWidget(window.build_reset_button())
    actions.addStretch()
    actions.addWidget(window.save_settings_button)
    container = QWidget()
    container.setLayout(body)

    window.settings_dialog = QDialog(window)
    window.settings_dialog.setWindowTitle("自动排版参数设置")
    window.settings_dialog.resize(820, 620)

    def save_and_return() -> None:
        window.save_layout_preferences()
        window.settings_dialog.accept()

    window.save_settings_button.clicked.connect(save_and_return)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(container)
    dialog_layout = QVBoxLayout(window.settings_dialog)
    dialog_layout.addWidget(scroll)
    dialog_layout.addLayout(actions)

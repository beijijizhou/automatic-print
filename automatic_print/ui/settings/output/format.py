"""Build the canonical output format and its main-workbench mirror."""
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from ....layout_engine import png_engine_name


def build_output_settings(window):
    compression = QComboBox()
    compression.addItem("等级 1 — 轻度压缩（推荐）", 1)
    compression.addItem("等级 0 — 不压缩（文件最大）", 0)
    compression.addItem("等级 3 — 中度压缩（文件更小）", 3)
    output_format = QComboBox()
    output_format.addItem("PNG（生产默认）", "png")
    output_format.addItem("并行分块 TIFF（实验）", "tiff")
    engine = QComboBox()
    engine.addItem("标准快速模式（推荐）", "pillow")
    if png_engine_name() == "大图节省内存模式":
        engine.addItem("大图节省内存模式", "libvips")
    window.png_compression = compression
    window.output_format = output_format
    window.png_engine = engine


def build_quick_output_format(window):
    """Expose the developer TIFF selector in the main parameter area."""
    control = QWidget()
    row = QHBoxLayout(control)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    row.addWidget(QLabel('输出格式'))
    quick = QComboBox()
    quick.addItem('PNG', 'png')
    quick.addItem('TIFF（并行分块）', 'tiff')
    quick.setToolTip('TIFF 为开发者测试格式；PNG 仍是生产默认格式。')
    quick.setCurrentIndex(max(0, quick.findData(window.output_format.currentData())))

    def set_canonical(_index):
        target = window.output_format.findData(quick.currentData())
        if target >= 0:
            window.output_format.setCurrentIndex(target)

    def set_quick(_index):
        target = quick.findData(window.output_format.currentData())
        if target >= 0:
            quick.setCurrentIndex(target)

    quick.currentIndexChanged.connect(set_canonical)
    window.output_format.currentIndexChanged.connect(set_quick)
    row.addWidget(quick)
    window.quick_output_format = quick
    window.quick_output_format_group = control
    control.hide()
    return control

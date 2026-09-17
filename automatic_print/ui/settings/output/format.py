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

    def riin_active():
        return window.cutter_settings.mode.currentData() != 'free'

    def set_canonical(_index):
        selected = 'png' if riin_active() else quick.currentData()
        target = window.output_format.findData(selected)
        if target >= 0:
            window.output_format.setCurrentIndex(target)
        if selected != quick.currentData():
            quick.setCurrentIndex(max(0, quick.findData(selected)))

    def set_quick(_index):
        target = quick.findData(window.output_format.currentData())
        if target >= 0:
            quick.setCurrentIndex(target)

    quick.currentIndexChanged.connect(set_canonical)
    window.output_format.currentIndexChanged.connect(set_quick)

    def sync_riin_compatibility():
        blocked = riin_active()
        for combo in (window.output_format, quick):
            index = combo.findData('tiff')
            item = combo.model().item(index) if index >= 0 else None
            if item is not None:
                item.setEnabled(not blocked)
            if blocked and combo.currentData() == 'tiff':
                combo.setCurrentIndex(max(0, combo.findData('png')))
        quick.setToolTip(
            'RIIN切膜只支持PNG；切换到自由排版后可使用TIFF性能测试。'
            if blocked else 'TIFF仅用于开发者自由排版性能测试；PNG是生产格式。'
        )

    window.cutter_settings.mode.currentIndexChanged.connect(
        lambda _index: sync_riin_compatibility()
    )
    row.addWidget(quick)
    window.quick_output_format = quick
    window.quick_output_format_group = control
    sync_riin_compatibility()
    control.hide()
    return control

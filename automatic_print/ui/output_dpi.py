"""Source-following mode and persistent manual DPI in one output control."""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QCheckBox


def build_output_dpi(window):
    field = QWidget()
    layout = QHBoxLayout(field)
    layout.setContentsMargins(0, 0, 0, 0)
    window.follow_source_dpi = QCheckBox('跟随原图DPI（默认）')
    window.follow_source_dpi.setChecked(window.preferences.value('layout/follow_source_dpi', True, bool))
    window.dpi.setEnabled(not window.follow_source_dpi.isChecked())
    window.dpi.setToolTip('取消跟随原图后手动指定输出DPI；始终保持实际打印尺寸。')
    window.follow_source_dpi.setToolTip('批次DPI一致时沿用原图；混合DPI或缺失时提示手动选择，不猜测。')
    def changed(checked):
        window.dpi.setEnabled(not checked)
        window.preferences.setValue('layout/follow_source_dpi', checked)
    window.follow_source_dpi.toggled.connect(changed)
    layout.addWidget(window.follow_source_dpi)
    layout.addWidget(window.dpi)
    return field

"""Persistent minimum label-to-artwork gap, configured with layout rules."""
from PySide6.QtWidgets import QDoubleSpinBox


def build_header_gap(window):
    field = QDoubleSpinBox()
    field.setRange(0, 200)
    field.setDecimals(1)
    field.setSuffix(' 毫米')
    field.setValue(window.preferences.value('layout/membrane_gap_mm', 40, float))
    field.setToolTip('补足膜标签与下方图案之间的透明空白，不缩放图案；0表示关闭。原文件不修改。')
    field.valueChanged.connect(lambda value: window.preferences.setValue('layout/membrane_gap_mm', value))
    window.membrane_gap = field
    return field

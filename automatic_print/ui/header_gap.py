"""Persistent minimum label-to-artwork gap, configured with layout rules."""
from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QWidget, QHBoxLayout, QLabel


def build_header_gap(window):
    from .width_fit import build_width_fit
    build_width_fit(window)
    enabled = QCheckBox('启用膜标签/二维码与图案间距补足')
    legacy = window.preferences.value('developer/membrane_gap_enabled', False, bool)
    enabled.setChecked(window.preferences.value('layout/membrane_gap_enabled', legacy, bool))
    enabled.toggled.connect(
        lambda value: window.preferences.setValue('layout/membrane_gap_enabled', value))
    window.membrane_gap_enabled = enabled
    field = QDoubleSpinBox()
    field.setRange(0, 200)
    field.setDecimals(1)
    field.setSuffix(' 毫米')
    field.setValue(window.preferences.value('layout/membrane_gap_mm', 40, float))
    field.setToolTip('补足膜标签与下方图案之间的透明空白，不缩放图案；0表示关闭。原文件不修改。')
    field.valueChanged.connect(lambda value: window.preferences.setValue('layout/membrane_gap_mm', value))
    field.setEnabled(enabled.isChecked())
    enabled.toggled.connect(field.setEnabled)
    window.membrane_gap = field
    return field


def build_quick_header_gap(window):
    """Mirror the canonical setting without moving it out of print settings."""
    group = QWidget()
    row = QHBoxLayout(group)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(QLabel('膜标签与图案间距'))
    enabled = QCheckBox('启用补足')
    enabled.setChecked(window.membrane_gap_enabled.isChecked())
    enabled.toggled.connect(window.membrane_gap_enabled.setChecked)
    window.membrane_gap_enabled.toggled.connect(enabled.setChecked)
    row.addWidget(enabled)
    field = QDoubleSpinBox()
    field.setRange(window.membrane_gap.minimum(), window.membrane_gap.maximum())
    field.setDecimals(1)
    field.setSuffix(' 毫米')
    field.setValue(window.membrane_gap.value())
    field.setToolTip(window.membrane_gap.toolTip())
    field.valueChanged.connect(window.membrane_gap.setValue)
    window.membrane_gap.valueChanged.connect(field.setValue)
    row.addWidget(field)
    window.quick_membrane_gap = field
    window.quick_membrane_gap_enabled = enabled
    field.setEnabled(enabled.isChecked())
    enabled.toggled.connect(field.setEnabled)
    window.quick_header_gap_group = group
    group.hide()
    return group

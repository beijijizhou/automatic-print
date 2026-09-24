"""Editable main-page mirrors for the canonical cutter settings."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QGridLayout, QLabel, QPushButton, QWidget,
)

from .spinbox_style import double_spinbox


def _mirrored_spin(source):
    control = double_spinbox(
        source.value(), source.minimum(), source.maximum(),
        decimals=source.decimals(),
    )
    control.setSuffix(source.suffix())
    control.setToolTip(source.toolTip())
    control.valueChanged.connect(source.setValue)
    source.valueChanged.connect(control.setValue)
    return control


def build_quick_cutter_settings(window, gap_control):
    cutter = window.cutter_settings
    panel = QWidget()
    grid = QGridLayout(panel)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(7)

    status = QLabel()
    status.setTextInteractionFlags(Qt.TextSelectableByMouse)
    status.setWordWrap(True)
    grid.addWidget(status, 0, 0, 1, 6)
    grid.addWidget(gap_control, 1, 0, 1, 3)

    knife_mode = QComboBox()
    knife_mode.addItem('自动计算统一刀位', True)
    knife_mode.addItem('手动刀位', False)
    knife_mode.setCurrentIndex(0 if cutter.auto_knife.isChecked() else 1)
    knife_mode.currentIndexChanged.connect(
        lambda: cutter.auto_knife.setChecked(bool(knife_mode.currentData())))

    knife = _mirrored_spin(cutter.knife)
    knife.setSuffix(' 毫米')
    left_lift = _mirrored_spin(cutter.left_marker_lift)
    left_lift.setSuffix(' 毫米')
    stop_gap = _mirrored_spin(cutter.knife_change_gap)
    stop_gap.setSuffix(' 毫米')

    grid.addWidget(QLabel('刀位方式'), 1, 3)
    grid.addWidget(knife_mode, 1, 4, 1, 2)
    grid.addWidget(QLabel('手动刀位'), 2, 0)
    grid.addWidget(knife, 2, 1)
    grid.addWidget(QLabel('左刀码高于图片'), 2, 2)
    grid.addWidget(left_lift, 2, 3)
    grid.addWidget(QLabel('换刀/批次结束停止距离'), 2, 4)
    grid.addWidget(stop_gap, 2, 5)

    color_settings = QPushButton('识别色块设置…')
    color_settings.clicked.connect(window.color_block_settings.show)
    full_settings = QPushButton('完整切膜机参数…')

    def open_full_settings():
        window.print_settings_tabs.setCurrentIndex(0)
        window.open_settings_dialog()

    full_settings.clicked.connect(open_full_settings)
    grid.addWidget(color_settings, 3, 4)
    grid.addWidget(full_settings, 3, 5)

    def sync(*_args):
        cutting = cutter.mode.currentData() != 'free'
        expected = 0 if cutter.auto_knife.isChecked() else 1
        if knife_mode.currentIndex() != expected:
            knife_mode.blockSignals(True)
            knife_mode.setCurrentIndex(expected)
            knife_mode.blockSignals(False)
        knife.setEnabled(cutting and not cutter.auto_knife.isChecked())
        for control in (knife_mode, left_lift, stop_gap, color_settings):
            control.setEnabled(cutting)
        gap_control.setVisible(cutting)
        status.setText(
            f'膜规格：{cutter.film.currentText()}　'
            f'模式：{cutter.mode.currentText()}　'
            f'有效画布：{cutter.printable.usable_width():g} 毫米'
        )

    cutter.mode.currentIndexChanged.connect(sync)
    cutter.film.currentIndexChanged.connect(sync)
    cutter.auto_knife.toggled.connect(sync)
    cutter.printable.left.valueChanged.connect(sync)
    cutter.printable.right.valueChanged.connect(sync)
    sync()

    window.quick_knife_mode = knife_mode
    window.quick_knife_position = knife
    window.quick_left_marker_lift = left_lift
    window.quick_knife_change_gap = stop_gap
    window.quick_cutter_status = status
    window.quick_color_block_settings = color_settings
    window.quick_full_cutter_settings = full_settings
    return panel

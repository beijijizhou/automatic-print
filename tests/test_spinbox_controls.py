import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt, QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication, QDoubleSpinBox, QSpinBox, QStyle, QStyleFactory,
    QStyleOptionSpinBox, QVBoxLayout, QWidget,
)
import pytest

from automatic_print.ui.workbench_style import WORKBENCH_STYLE
from automatic_print.ui.spinbox_style import spinbox_style

APP = QApplication.instance() or QApplication([])


@pytest.mark.parametrize('native_style', ['Fusion', 'Windows'])
@pytest.mark.parametrize('box_type', [QSpinBox, QDoubleSpinBox])
def test_visible_plus_minus_mouse_keyboard_and_limits(tmp_path, native_style, box_type):
    panel = QWidget()
    box = box_type()
    style = QStyleFactory.create(native_style)
    style.setParent(panel)
    panel.setStyle(style)
    panel.setStyleSheet(WORKBENCH_STYLE+spinbox_style())
    QVBoxLayout(panel).addWidget(box)
    box.setRange(0, 20)
    box.setValue(10)
    panel.resize(300, 90)
    panel.show()
    APP.processEvents()
    option = QStyleOptionSpinBox()
    box.initStyleOption(option)
    for control, expected in ((QStyle.SC_SpinBoxUp, 11), (QStyle.SC_SpinBoxDown, 10)):
        rect = box.style().subControlRect(QStyle.CC_SpinBox, option, control, box)
        assert rect.width() >= 28 and rect.height() >= 18
        assert box.rect().contains(rect.center())
        QTest.mouseClick(box, Qt.LeftButton, pos=rect.center())
        assert box.value() == expected
    box.setFocus()
    QTest.keyClick(box, Qt.Key_Up)
    assert box.value() == 11
    QTest.keyClick(box, Qt.Key_Down)
    assert box.value() == 10
    box.setValue(20)
    QTest.keyClick(box, Qt.Key_Up)
    assert box.value() == 20
    box.setValue(0)
    QTest.keyClick(box, Qt.Key_Down)
    assert box.value() == 0
    box.setValue(10)
    assert panel.grab().save(str(tmp_path/'spin-controls.png'))
    panel.close()


def test_real_settings_window_step_changes_canonical_parameter(tmp_path):
    from automatic_print.ui.main_window import MainWindow
    window = MainWindow(QSettings(str(tmp_path/'params.ini'), QSettings.IniFormat))
    window.startup_update_timer.stop()
    window.settings_dialog.show()
    APP.processEvents()
    box = window.spacing
    box.setValue(5)
    option = QStyleOptionSpinBox()
    box.initStyleOption(option)
    for control, expected in ((QStyle.SC_SpinBoxUp, 6), (QStyle.SC_SpinBoxDown, 5)):
        rect = box.style().subControlRect(QStyle.CC_SpinBox, option, control, box)
        assert rect.width() >= 28
        QTest.mouseClick(box, Qt.LeftButton, pos=rect.center())
        assert window._layout_settings().spacing_mm == expected
    window.close()

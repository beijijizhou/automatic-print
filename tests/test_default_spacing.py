import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QLabel
from automatic_print.layout import LayoutSettings
from automatic_print.ui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])
WINDOWS = []


def test_new_settings_default_to_five_mm_and_saved_value_survives(tmp_path):
    prefs = QSettings(str(tmp_path/'spacing.ini'), QSettings.IniFormat)
    assert LayoutSettings().spacing_mm == 5
    window = MainWindow(prefs)
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    assert window.spacing.value() == 5
    assert window._layout_settings().spacing_mm == 5
    assert any(label.text() == '上下垂直间距（毫米）' for label in window.findChildren(QLabel))
    assert '水平距离由整批刀位' in window.spacing.toolTip()
    mode = window.cutter_settings.mode
    mode.setCurrentIndex(mode.findData('free'))
    assert any(label.text() == '自由排版图片间距（毫米）' for label in window.findChildren(QLabel))
    mode.setCurrentIndex(mode.findData('dual'))
    assert any(label.text() == '上下垂直间距（毫米）' for label in window.findChildren(QLabel))
    window.spacing.setValue(7)
    assert not window.cutter_settings.compare_films.isChecked()
    window.cutter_settings.compare_films.setChecked(True)
    assert window._layout_settings().compare_film_sizes
    assert window._layout_settings().riin_left_mm == 10
    window.close()
    reopened = MainWindow(prefs)
    WINDOWS.append(reopened)
    reopened.startup_update_timer.stop()
    assert reopened.spacing.value() == 7
    assert reopened._layout_settings().spacing_mm == 7
    assert reopened.cutter_settings.compare_films.isChecked()
    reopened.close()

import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
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
    window.spacing.setValue(7)
    window.close()
    reopened = MainWindow(prefs)
    WINDOWS.append(reopened)
    reopened.startup_update_timer.stop()
    assert reopened.spacing.value() == 7
    assert reopened._layout_settings().spacing_mm == 7
    reopened.close()

import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QLabel
from automatic_print.layout_engine import LayoutSettings
from automatic_print.ui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])
WINDOWS = []


def test_new_settings_default_to_eight_mm_and_saved_value_survives(tmp_path):
    prefs = QSettings(str(tmp_path/'spacing.ini'), QSettings.IniFormat)
    assert LayoutSettings().spacing_mm == 8
    window = MainWindow(prefs)
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    assert window.spacing.value() == 8
    assert window._layout_settings().spacing_mm == 8
    assert any(label.text() == '上下垂直间距（毫米）' for label in window.findChildren(QLabel))
    assert '水平距离由整批刀位' in window.spacing.toolTip()
    mode = window.cutter_settings.mode
    mode.setCurrentIndex(mode.findData('free'))
    assert any(label.text() == '自由排版图片间距（毫米）' for label in window.findChildren(QLabel))
    mode.setCurrentIndex(mode.findData('dual'))
    assert any(label.text() == '上下垂直间距（毫米）' for label in window.findChildren(QLabel))
    window.spacing.setValue(7)
    assert window.cutter_settings.compare_films.isChecked()
    window.cutter_settings.compare_films.setChecked(False)
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


def test_spacing_migration_once_preserves_other_custom_values(tmp_path):
    from automatic_print.ui.spacing_settings import migrate_spacing
    prefs = QSettings(str(tmp_path/'migration.ini'), QSettings.IniFormat)
    prefs.setValue('layout/spacing_mm', 5)
    migrate_spacing(prefs)
    assert prefs.value('layout/spacing_mm', type=float) == 8
    prefs.setValue('layout/spacing_mm', 5)
    migrate_spacing(prefs)
    assert prefs.value('layout/spacing_mm', type=float) == 5
    custom = QSettings(str(tmp_path/'custom.ini'), QSettings.IniFormat)
    custom.setValue('layout/spacing_mm', 12)
    migrate_spacing(custom)
    assert custom.value('layout/spacing_mm', type=float) == 12

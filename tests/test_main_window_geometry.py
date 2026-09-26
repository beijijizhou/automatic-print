import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QSizePolicy

from automatic_print.ui.main_window import MainWindow


APP = QApplication.instance() or QApplication([])


def test_main_window_can_fit_a_short_desktop(tmp_path):
    preferences = QSettings(
        str(tmp_path / "main-window.ini"), QSettings.IniFormat
    )
    preferences.setValue("department/current", "dtf")
    window = MainWindow(preferences)
    window.startup_update_timer.stop()
    window.show()
    APP.processEvents()

    assert window.workspace_tabs.sizePolicy().verticalPolicy() == QSizePolicy.Ignored
    assert window.minimumSizeHint().height() < 700
    assert window.font().pointSize() > 0

    window.preference_autosave.timer.stop()
    window.automation_home.label_quick_panel.preview.stop_loading()
    window.close()

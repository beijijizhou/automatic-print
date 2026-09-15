import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QPushButton

from automatic_print.ui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])
WINDOWS = []


def test_removed_batch_details_leave_only_developer_pages(tmp_path):
    window = MainWindow(QSettings(str(tmp_path/'details.ini'), QSettings.IniFormat))
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    window.show()
    APP.processEvents()
    panel = window.automation_home.label_quick_panel
    details = panel.details_dialog
    assert not hasattr(panel, 'details_button')
    assert details.tabs.count() == 0
    assert not details.isVisible() and not details.isModal()
    for tool in (panel.summary, panel.timings, panel.preview_tabs):
        assert tool.isVisible()
    assert window.batch_record.document() is window.run_log.document()
    assert panel.marker_examples.isVisible()
    panel.preview_tabs.setCurrentIndex(0)
    assert panel.preview_scroll.isVisible()
    window.developer_mode_checkbox.setChecked(True)
    panel.history_button.click()
    APP.processEvents()
    assert details.isVisible()
    assert [details.tabs.tabText(i) for i in range(details.tabs.count())] == ['排版历史']
    details.close()
    assert panel.summary.isVisible()
    assert panel.preview_scroll.isVisible()
    window.close()

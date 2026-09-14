import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from automatic_print.ui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])
OWNERS = []


def window(path):
    result = MainWindow(QSettings(str(path), QSettings.IniFormat))
    OWNERS.append(result)
    result.startup_update_timer.stop()
    result.show()
    APP.processEvents()
    return result


def test_default_hides_tools_and_gates_direct_open(tmp_path, monkeypatch):
    import automatic_print.ui.film_history as history
    monkeypatch.setattr(history, 'load_runs', lambda *_a: (_ for _ in ()).throw(AssertionError('history read')))
    owner = window(tmp_path/'prefs.ini')
    panel = owner.automation_home.label_quick_panel
    assert not owner.developer_mode_checkbox.isChecked()
    assert not panel.history_button.isVisible() and not panel.bulk_analysis_button.isVisible()
    panel.details_dialog.open_history()
    panel.details_dialog.open_bulk_analysis()
    assert not hasattr(panel.details_dialog, 'history_page')
    assert not hasattr(panel.details_dialog, 'bulk_dialog')
    assert panel.summary.isVisible() and panel.preview_scroll.isVisible()
    assert owner.developer_mode_checkbox.isVisible()
    assert owner.grab().save(str(tmp_path/'developer-off.png'))
    owner.close()


def test_toggle_persists_and_existing_history_tab_hides(tmp_path, monkeypatch):
    import automatic_print.history.store as store
    monkeypatch.setattr(store, 'log_folder', lambda: tmp_path)
    owner = window(tmp_path/'prefs.ini')
    panel = owner.automation_home.label_quick_panel
    owner.developer_mode_checkbox.setChecked(True)
    assert panel.history_button.isVisible() and panel.bulk_analysis_button.isVisible()
    panel.history_button.click()
    APP.processEvents()
    details = panel.details_dialog
    assert details.tabs.currentWidget() is details.history_page
    owner.developer_mode_checkbox.setChecked(False)
    assert not details.tabs.isTabVisible(details.tabs.indexOf(details.history_page))
    assert not panel.history_button.isVisible()
    details.close()
    owner.developer_mode_checkbox.setChecked(True)
    owner.close()
    restored = window(tmp_path/'prefs.ini')
    assert restored.developer_mode_checkbox.isChecked()
    assert restored.automation_home.label_quick_panel.bulk_analysis_button.isVisible()
    restored.close()


def test_active_developer_task_blocks_exit_and_mode_disable(tmp_path):
    owner = window(tmp_path/'prefs.ini')
    owner.developer_mode_checkbox.setChecked(True)
    details = owner.automation_home.label_quick_panel.details_dialog
    details.open_bulk_analysis()
    dialog = details.bulk_dialog
    assert '不生成最终文件' in dialog.windowTitle()
    dialog.thread = object()  # Represent a task pending cleanup, without a native thread.
    assert owner.has_active_tasks()
    owner.developer_mode_checkbox.setChecked(False)
    assert owner.developer_mode_checkbox.isChecked()
    owner.close()
    assert owner.isVisible()
    dialog.thread = None
    dialog.close()
    owner.developer_mode_checkbox.setChecked(False)
    assert not owner.has_active_tasks()
    owner.close()

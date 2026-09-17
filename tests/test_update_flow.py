import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from time import monotonic, sleep

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

from automatic_print.ui.main_window import MainWindow
from automatic_print.ui import update_actions
from automatic_print.updates.source import SourceUpdater, SourceUpdateInfo
from automatic_print.runtime import restart

APP = QApplication.instance() or QApplication([])
APP.setQuitOnLastWindowClosed(False)
WINDOWS = []  # Keep Qt owners alive across event dispatch in consecutive tests.


def test_normal_launch_discards_stale_development_restart_marker(
    tmp_path, monkeypatch,
):
    marker = tmp_path / '.restart-request'
    marker.touch()
    monkeypatch.setattr(restart, 'RESTART_REQUEST', marker)
    monkeypatch.delenv('AUTOMATIC_PRINT_DEV', raising=False)
    owner = object()

    timer = restart.install_restart_monitor(APP, owner)

    assert not marker.exists()
    assert not timer.isActive()


def test_runtime_and_development_launcher_share_restart_marker():
    import dev

    assert restart.RESTART_REQUEST == dev.RESTART_REQUEST


def wait_until(predicate):
    deadline = monotonic()+5
    while not predicate():
        assert monotonic() < deadline
        APP.processEvents()
        sleep(0.01)


def window_for_test(tmp_path, monkeypatch):
    window = MainWindow(QSettings(str(tmp_path/'update.ini'), QSettings.IniFormat))
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    window.show()
    monkeypatch.setattr(update_actions, 'source_install', lambda: True)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: pytest_fail())
    info = SourceUpdateInfo('old', 'new', '0.1.999', '2026-09-14', 2)
    monkeypatch.setattr(SourceUpdater, 'check', lambda self: info)
    return window, info


def test_button_updates_source_then_restarts_without_browser(tmp_path, monkeypatch):
    window, info = window_for_test(tmp_path, monkeypatch)
    applied, restarted = [], []
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Yes)
    monkeypatch.setattr(update_actions.QDesktopServices, 'openUrl',
                        lambda *args: (_ for _ in ()).throw(AssertionError('No installer browser')))
    monkeypatch.setattr(SourceUpdater, 'apply', lambda self, update: applied.append(update) or update)
    monkeypatch.setattr(update_actions, 'restart_updated_app', lambda w: restarted.append(w))
    window.check_update_button.click()
    wait_until(lambda: bool(restarted))
    assert applied == [info]
    assert restarted == [window]
    assert '安全重启' in window.update_status_label.text()
    assert window.update_thread is None
    window.close()


def test_single_click_applies_after_confirmation_runs_nested_event_loop(tmp_path, monkeypatch):
    window, info = window_for_test(tmp_path, monkeypatch)
    applied, restarted = [], []
    def confirm(*args):
        # A real modal dialog pumps events: the check thread can finish and its
        # cleanup run before the user presses Yes. Never lose the continuation.
        wait_until(lambda: window.update_thread is None)
        APP.processEvents()
        return QMessageBox.Yes
    monkeypatch.setattr(QMessageBox, 'question', confirm)
    monkeypatch.setattr(SourceUpdater, 'apply', lambda self, update: applied.append(update) or update)
    monkeypatch.setattr(update_actions, 'restart_updated_app', lambda w: restarted.append(w))
    window.check_update_button.click()
    wait_until(lambda: bool(restarted))
    assert applied == [info]
    assert restarted == [window]
    window.close()


def test_declining_update_does_not_apply_or_leave_pending_state(tmp_path, monkeypatch):
    window, _info = window_for_test(tmp_path, monkeypatch)
    applied = []
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.No)
    monkeypatch.setattr(SourceUpdater, 'apply', lambda self, info: applied.append(info))
    window.check_update_button.click()
    wait_until(lambda: window.update_thread is None and window.check_update_button.isEnabled())
    assert applied == []
    assert window.pending_source_update is None
    assert window.completed_source_check is None
    window.close()


def test_busy_production_task_never_applies_update(tmp_path, monkeypatch):
    window, info = window_for_test(tmp_path, monkeypatch)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: pytest_fail())
    window.thread = object()
    window.check_for_updates(False)
    wait_until(lambda: window.update_thread is None)
    assert window.pending_source_update is None
    assert '等待排版' in window.update_status_label.text()
    assert not window.source_update_applying
    window.thread = None
    window.close()


def pytest_fail():
    raise AssertionError('Busy update must not ask to apply')


def test_silent_check_only_displays_available_code(tmp_path, monkeypatch):
    window, info = window_for_test(tmp_path, monkeypatch)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: pytest_fail())
    window.check_for_updates(True)
    wait_until(lambda: window.update_thread is None)
    assert '2026-09-14' in window.update_status_label.text()
    assert window.pending_source_update is None
    window.close()


def test_failed_apply_restores_controls_and_shows_retry(tmp_path, monkeypatch):
    window, _info = window_for_test(tmp_path, monkeypatch)
    warnings = []
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[-1]))
    def fail_apply(self, info):
        raise ValueError('依赖同步失败')
    monkeypatch.setattr(SourceUpdater, 'apply', fail_apply)
    window.check_for_updates(False)
    wait_until(lambda: bool(warnings) and window.update_thread is None
               and not window.source_update_applying)
    assert window.automation_home.isEnabled()
    assert window.settings_dialog.isEnabled()
    assert window.check_update_button.isEnabled()
    assert '重试' in window.update_status_label.text()
    window.close()

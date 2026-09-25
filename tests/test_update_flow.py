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
    monkeypatch.setattr(restart, 'SOURCE_VERSION_FILE', tmp_path/'missing-version.py')
    monkeypatch.delenv('AUTOMATIC_PRINT_DEV', raising=False)
    owner = object()

    timer = restart.install_restart_monitor(APP, owner)

    assert not marker.exists()
    assert not timer.isActive()


def test_external_source_update_waits_for_active_job_then_restarts(tmp_path, monkeypatch):
    marker = tmp_path/'.restart-request'
    version_file = tmp_path/'__init__.py'
    version_file.write_text(f'__version__ = "{restart.__version__}"\n', encoding='utf-8')
    monkeypatch.setattr(restart, 'RESTART_REQUEST', marker)
    monkeypatch.setattr(restart, 'SOURCE_VERSION_FILE', version_file)
    monkeypatch.setattr(restart, 'UPDATE_GUARD', tmp_path/'.update-in-progress')
    monkeypatch.delenv('AUTOMATIC_PRINT_DEV', raising=False)
    calls = []

    class Owner:
        active = True
        update_thread = None

        def has_active_tasks(self):
            return self.active

        def source_update_busy(self):
            return False

        def show_update_progress(self, message):
            calls.append(message)

    owner = Owner()
    monkeypatch.setattr(restart, 'request_application_restart',
                        lambda window: calls.append('restart') or True)
    timer = restart.install_restart_monitor(APP, owner)
    try:
        assert timer.isActive()
        version_file.write_text('__version__ = "0.1.999"\n', encoding='utf-8')
        timer.timeout.emit()  # first observation is deliberately not actionable
        assert not calls
        timer.timeout.emit()
        assert calls == ['源码已更新；当前任务完成后自动安全重启…']
        owner.active = False
        timer.timeout.emit()
        assert calls[-2:] == ['源码已更新；正在安全重启以加载新版本…', 'restart']
        assert not timer.isActive()
    finally:
        timer.stop()


def test_external_source_update_waits_for_update_guard(tmp_path, monkeypatch):
    marker = tmp_path/'.restart-request'
    version_file = tmp_path/'__init__.py'
    version_file.write_text('__version__ = "0.1.999"\n', encoding='utf-8')
    guard = tmp_path/'.update-in-progress'
    guard.touch()
    monkeypatch.setattr(restart, 'RESTART_REQUEST', marker)
    monkeypatch.setattr(restart, 'SOURCE_VERSION_FILE', version_file)
    monkeypatch.setattr(restart, 'UPDATE_GUARD', guard)
    monkeypatch.delenv('AUTOMATIC_PRINT_DEV', raising=False)
    calls = []

    class Owner:
        update_thread = None

        def has_active_tasks(self):
            return False

        def source_update_busy(self):
            return False

        def show_update_progress(self, message):
            calls.append(message)

    monkeypatch.setattr(restart, 'request_application_restart',
                        lambda window: calls.append('restart') or True)
    timer = restart.install_restart_monitor(APP, Owner())
    try:
        timer.timeout.emit()
        timer.timeout.emit()
        assert not calls
        guard.unlink()
        timer.timeout.emit()
        assert not calls
        timer.timeout.emit()
        assert calls[-1] == 'restart'
    finally:
        timer.stop()


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
    window.check_for_updates(False)
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
    window.check_for_updates(False)
    wait_until(lambda: bool(restarted))
    assert applied == [info]
    assert restarted == [window]
    window.close()


def test_declining_update_does_not_apply_or_leave_pending_state(tmp_path, monkeypatch):
    window, _info = window_for_test(tmp_path, monkeypatch)
    applied = []
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.No)
    monkeypatch.setattr(SourceUpdater, 'apply', lambda self, info: applied.append(info))
    window.check_for_updates(False)
    wait_until(lambda: window.update_thread is None
               and window.completed_source_check is None)
    assert applied == []
    assert window.pending_source_update is None
    assert window.completed_source_check is None
    assert not any(
        item['key'] == 'app-update'
        for item in window.activity_hub.snapshot()['activities']
    )
    assert window.global_activity_center.grab().save(
        str(tmp_path/'production-tasks-only.png')
    )
    window.close()


def test_busy_production_task_never_applies_update(tmp_path, monkeypatch):
    window, info = window_for_test(tmp_path, monkeypatch)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: pytest_fail())
    window.thread = object()
    window.check_for_updates(False)
    wait_until(lambda: window.update_thread is None
               and window.completed_source_check is None)
    assert window.pending_source_update is None
    assert '生产任务结束后' in window.update_status_label.text()
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
    assert not any(
        item['key'] == 'app-update'
        for item in window.activity_hub.snapshot()['activities']
    )
    assert window.pending_source_update is None
    window.close()


def test_checkout_latest_is_not_reported_as_loaded_version(tmp_path, monkeypatch):
    window, _info = window_for_test(tmp_path, monkeypatch)
    monkeypatch.setattr(update_actions, 'source_code_changed', lambda: True)
    current = SourceUpdateInfo('same', 'same', '0.1.999', '2026-09-19', 0,
                               release_iteration=8)
    window.update_check_finished(current)
    assert '自动安全重启' in window.update_status_label.text()
    assert '源码已是最新' not in window.update_status_label.text()
    window.confirm_source_check(current)
    assert '自动安全重启' in window.update_status_label.text()
    window.close()


def test_passive_update_check_does_not_block_layout(tmp_path, monkeypatch):
    window, _info = window_for_test(tmp_path, monkeypatch)
    window.update_thread = object()

    window.source_update_applying = False
    assert not window.has_active_tasks()

    window.source_update_applying = True
    assert window.has_active_tasks()
    window.update_thread = None
    window.source_update_applying = False
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
    assert not hasattr(window, 'check_update_button')
    assert '重试' in window.update_status_label.text()
    window.close()

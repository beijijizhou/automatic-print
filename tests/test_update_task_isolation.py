from PySide6.QtWidgets import QMessageBox

from automatic_print.updates.source import SourceUpdater
from test_update_flow import wait_until, window_for_test


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
    assert window.check_update_button.isVisible()
    assert window.check_update_button.isEnabled()
    assert window.check_update_button.text() == '检查更新'
    assert not hasattr(window, 'update_status_label')
    window.close()

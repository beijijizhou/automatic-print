import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from automatic_print.ui.main_window import MainWindow


APP = QApplication.instance() or QApplication([])


def make_window(tmp_path):
    window = MainWindow(QSettings(str(tmp_path/'spinner.ini'), QSettings.IniFormat))
    window.startup_update_timer.stop()
    window.show()
    APP.processEvents()
    return window


def test_unknown_progress_updates_hidden_legacy_state_without_duplicate_spinner(tmp_path):
    window = make_window(tmp_path)
    window.started_at = window.stage_started_at = 1
    window.update_progress('保存图片', 390_000_000, 0, 'batch.png')
    APP.processEvents()
    assert not window.busy_spinner.isActive()
    assert not window.busy_spinner.isVisible()
    assert not window.progress.isVisible()
    assert '保存图片' in window.status.text()
    window.update_progress('分析批次', 0, 0, 'batch')
    assert not window.busy_spinner.isActive()
    window.generation_cancelled()
    assert not window.busy_spinner.isActive()
    assert not window.progress.isVisible()
    assert window.progress.format() == '已停止'
    window.close()


def test_known_progress_keeps_hidden_percentage_value_for_reports(tmp_path):
    window = make_window(tmp_path)
    window.started_at = window.stage_started_at = 1
    window.update_progress('测量标签与刀码', 5, 10, 'sample.png')
    APP.processEvents()
    assert not window.busy_spinner.isActive()
    assert not window.busy_spinner.isVisible()
    assert not window.progress.isVisible()
    assert window.progress.maximum() == 100
    assert '%' in window.progress.format()
    window.close()

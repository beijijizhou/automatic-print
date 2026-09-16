import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from threading import Event, get_ident
from PIL import Image
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from automatic_print.ui.main_window import MainWindow
from automatic_print.ui.previews.runtime import task as preview_task
from preview_wait import wait_preview


def test_saved_folder_does_not_block_startup_and_stale_results_are_ignored(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    first, second = tmp_path/'first', tmp_path/'second'
    for folder in (first, second):
        folder.mkdir()
        Image.new('RGBA', (80, 120), 'blue').save(folder/'B1-1-T-White-M-NO1-1.png',
                                                      dpi=(25.4, 25.4))
    entered, release = Event(), Event()
    calls, thread_ids = [], []
    original = preview_task.discover_images

    def slow_scan(folder):
        calls.append(folder)
        thread_ids.append(get_ident())
        if folder == first:
            entered.set()
            assert release.wait(5)
        return original(folder)

    monkeypatch.setattr(preview_task, 'discover_images', slow_scan)
    prefs = QSettings(str(tmp_path/'startup.ini'), QSettings.IniFormat)
    prefs.setValue('source_location', str(first))
    prefs.setValue('label/enabled', False)
    prefs.setValue('cutter/mode', 'free')  # Solid fixtures contain no cutter-label header.
    prefs.setValue('cutter/quick_mode', False)  # Advanced auto-preview remains available.
    window = MainWindow(prefs)
    window.startup_update_timer.stop()
    assert calls == []  # No file discovery, thumbnail decoding, or layout in constructor.
    window.show()
    panel = window.automation_home.label_quick_panel
    ticks = []
    timer = QTimer(window)
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    try:
        QTest.qWait(250)
        assert calls == []
        assert not panel.preview.refresh_timer.isActive()
        window.spacing.setValue(9)
        panel.preview.set_overview(False)
        QTest.qWait(200)
        assert calls == []  # Startup and editing parameters do not load remembered data.
        assert window.folder.text() == str(first)
        panel.read_folder_button.click()
        # The debounce itself is 250ms; allow bounded scheduler latency on cold startup.
        for _ in range(100):
            if entered.is_set():
                break
            QTest.qWait(20)
        assert entered.is_set()
        assert window.isVisible()
        assert ticks  # GUI event loop remains responsive while disk scan is blocked.
        assert '扫描文件夹' in panel.summary.progress.text()
        assert thread_ids[0] != get_ident()
        window.folder.setText(str(second))
        release.set()
        wait_preview(panel.preview)
        assert all(path.parent == second for path, _ in panel.preview.planned)
        assert 'second' in panel.summary.info.text()
        assert '预览完成' in panel.summary.progress.text()
        assert calls.count(second) == 1
        # Selection uses the existing plan, never another whole-batch calculation.
        count = len(calls)
        panel.manual_rotation.show_selected()
        QTest.qWait(150)
        assert len(calls) == count
    finally:
        release.set()
        timer.stop()
        window.close()


def test_stop_cancels_pending_refresh_without_restarting(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(QSettings(str(tmp_path/'empty.ini'), QSettings.IniFormat))
    window.startup_update_timer.stop()
    preview = window.automation_home.label_quick_panel.preview
    preview.use_folder(tmp_path)
    preview.stop_loading()
    QTest.qWait(200)
    assert not preview.refresh_timer.isActive()
    assert not preview.loader.active
    assert '停止' in preview.production_stage
    window.close()

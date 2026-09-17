import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QFileDialog

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.ui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])
WINDOWS = []


def make_window(tmp_path):
    window = MainWindow(QSettings(str(tmp_path/'direct.ini'), QSettings.IniFormat))
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    window.show()
    APP.processEvents()
    return window


def test_main_start_uses_unified_batch_entry_without_settings(tmp_path, monkeypatch):
    window = make_window(tmp_path)
    source = tmp_path/'selected-batch'
    source.mkdir()
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: str(source))
    calls = []
    monkeypatch.setattr(
        'automatic_print.ui.bulk_workbench.start_bulk',
        lambda owner, directory: calls.append((owner, directory)),
    )
    window.automation_home.start_layout_button.click()
    assert calls == [(window, str(source))]
    assert not window.settings_dialog.isVisible()
    for control in (window.progress, window.status, window.current_file):
        assert not control.isVisible()
        assert not window.settings_dialog.isAncestorOf(control)
    assert window.stop_generation_button.isVisible()
    assert not window.settings_dialog.isAncestorOf(window.stop_generation_button)
    assert not window.run_log.isVisible()
    assert not window.settings_dialog.isAncestorOf(window.run_log)
    window.close()


def test_cancel_folder_does_not_generate_old_batch(tmp_path, monkeypatch):
    window = make_window(tmp_path)
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *args: '')
    calls = []
    monkeypatch.setattr(window, 'generate', lambda: calls.append('generate'))
    window.automation_home.open_manual_layout()
    assert calls == []
    assert not window.settings_dialog.isVisible()
    window.close()


def test_composition_progress_and_saving_keep_current_batch(tmp_path):
    window = make_window(tmp_path)
    source = tmp_path/'batch'
    source.mkdir()
    paths = []
    for i in range(2):
        path = source/f'B{i}-1-T-Black-M-NO1-1.png'
        Image.new('RGBA', (40, 60), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    payloads = []
    generate_layout(paths, tmp_path/'out', LayoutSettings(
        dpi=25.4, cutter_mode='dual', number_images=False), plan_ready=payloads.append)
    window.folder.setText(str(source))
    controller = window.generation_preview
    controller.start()
    assert not window.automation_home.start_layout_button.isEnabled()
    controller.ready(payloads[0])
    controller.progress('合成图片', 1, 2, paths[0].name)
    assert controller.preview.composed_count == 1
    assert len(controller.preview.planned) == 2
    controller.progress('合成图片', 2, 2, paths[1].name)
    controller.progress('保存图片', 0, 100, 'batch.png')
    assert controller.preview.composed_count == 2
    assert '保存图片' in controller.panel.summary.progress.text()
    assert not window.settings_dialog.isVisible()
    controller.end()
    assert controller.preview.composed_count is None
    assert window.automation_home.start_layout_button.isEnabled()
    assert len(controller.preview.planned) == 2
    window.close()

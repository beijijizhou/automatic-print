import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pathlib import Path
from time import monotonic, sleep
from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

from automatic_print.ui.main_window import MainWindow
from automatic_print.ui import generation_actions
from automatic_print.layout_engine.intake.discovery import batch_discovery

APP = QApplication.instance() or QApplication([])
WINDOWS = []


def test_quick_default_overrides_old_rotation_and_persists(tmp_path):
    prefs = QSettings(str(tmp_path/'quick.ini'), QSettings.IniFormat)
    prefs.setValue('cutter/rotation_zone', True)
    window = MainWindow(prefs)
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    assert window.cutter_settings.quick_mode.isChecked()
    assert not window._layout_settings().cutter_rotation_zone
    assert not window._layout_settings().allow_rotation
    assert window._layout_settings().cutter_auto_knife
    window.cutter_settings.quick_mode.setChecked(False)
    window.cutter_settings.rotation_zone.setChecked(True)
    assert window._layout_settings().cutter_rotation_zone
    window.close()
    reopened = MainWindow(prefs)
    WINDOWS.append(reopened)
    reopened.startup_update_timer.stop()
    assert not reopened.cutter_settings.quick_mode.isChecked()
    assert reopened._layout_settings().cutter_rotation_zone
    reopened.close()


def test_selected_scan_is_reused_without_automatic_preview(tmp_path, monkeypatch):
    source = tmp_path/'orders'/'batch'
    source.mkdir(parents=True)
    paths = []
    for face in (1, 2):
        path = source/f'B123-1-T-Black-M-NO1-{face}.png'
        Image.new('RGBA', (40, 60), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    prefs = QSettings(str(tmp_path/'run.ini'), QSettings.IniFormat)
    prefs.setValue('label/enabled', False)
    prefs.setValue('layout/dpi', 25)
    window = MainWindow(prefs)
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    window.show()
    scans, errors = [], []
    original = batch_discovery.scan_batches
    selected_scan = original(source)
    def scan(folder, *args, **kwargs):
        scans.append(folder)
        return original(folder, *args, **kwargs)
    monkeypatch.setattr(batch_discovery, 'scan_batches', scan)
    # Whole-batch rotation comparisons are now allowed; folder loading stays explicit.
    from automatic_print.ui import failure_dialog
    monkeypatch.setattr(failure_dialog, 'show_failure_dialog', lambda *args: errors.append(args[-1]))
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: None)
    monkeypatch.setattr(generation_actions.QDesktopServices, 'openUrl', lambda *args: True)
    window.folder.setText(str(source))
    preview = window.generation_preview.preview
    assert not preview.refresh_timer.isActive()
    assert preview.loader.active is None
    window.spacing.setValue(9)
    assert not preview.refresh_timer.isActive()
    from PySide6.QtWidgets import QFileDialog
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *args: str(source))
    monkeypatch.setattr('automatic_print.ui.batch_folder_selection.choose_batch_folders',
                        lambda *_args: selected_scan)
    window.automation_home.start_layout_button.click()
    deadline = monotonic()+5
    while (not hasattr(window, 'bulk_controller')
           or window.bulk_controller.thread is not None):
        assert monotonic() < deadline
        APP.processEvents()
        sleep(0.01)
    assert not errors
    assert scans == []
    assert window.bulk_controller.worker is None
    assert len(preview.planned) == 2
    assert window.generation_preview.payload['order_check']['double_pairs'] == 1
    assert list(Path(window.job_path.text()).rglob('*.png'))
    assert '2 张' in window.automation_home.label_quick_panel.summary.info.text()
    window.close()

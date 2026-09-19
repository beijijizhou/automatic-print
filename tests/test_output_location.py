import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from time import monotonic, sleep
from pathlib import Path
from PIL import Image

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox
from automatic_print.layout_engine import LayoutSettings
from automatic_print.ui import generation_actions
from automatic_print.ui.main_window import MainWindow
from automatic_print.ui.settings.output import output_base

APP = QApplication.instance() or QApplication([])
WINDOWS = []


def make_window(prefs):
    window = MainWindow(prefs)
    WINDOWS.append(window)
    window.startup_update_timer.stop()
    return window


def test_default_follows_source_parent_instead_of_old_desktop(tmp_path):
    prefs = QSettings(str(tmp_path/'defaults.ini'), QSettings.IniFormat)
    prefs.setValue('output_location', str(tmp_path/'old_desktop'))
    source = tmp_path/'orders'/'batch123'
    prefs.setValue('source_location', str(source))
    window = make_window(prefs)
    assert window.output_beside_source.isChecked()
    assert output_base(window, source) == source.parent
    assert window.output_location.text() == str(source.parent)
    assert window.output_location.isReadOnly()
    assert window.generation_preview.preview.source_folder is None
    other = tmp_path/'new_orders'/'batch456'
    window.folder.setText(str(other))
    assert window.output_location.text() == str(other.parent)
    assert output_base(window, other) == other.parent
    window.close()


def test_custom_override_survives_toggle_and_restart(tmp_path):
    prefs = QSettings(str(tmp_path/'custom.ini'), QSettings.IniFormat)
    window = make_window(prefs)
    source = tmp_path/'orders'/'batch'
    custom = tmp_path/'custom'
    window.folder.setText(str(source))
    window.output_beside_source.setChecked(False)
    window.output_location.setText(str(custom))
    assert output_base(window, source) == custom
    window.output_beside_source.setChecked(True)
    assert window.output_location.text() == str(source.parent)
    window.close()
    reopened = make_window(prefs)
    assert reopened.output_beside_source.isChecked()
    reopened.output_beside_source.setChecked(False)
    assert reopened.output_location.text() == str(custom)
    reopened.close()
    manual = make_window(prefs)
    assert not manual.output_beside_source.isChecked()
    assert output_base(manual, source) == custom
    manual.close()


def test_generated_png_is_beside_source_in_independent_job(tmp_path, monkeypatch):
    prefs = QSettings(str(tmp_path/'generate.ini'), QSettings.IniFormat)
    source = tmp_path/'orders'/'batch123'
    source.mkdir(parents=True)
    image = source/'B123-1-T-Black-M-NO1-1.png'
    Image.new('RGBA', (40, 60), 'blue').save(image, dpi=(25.4, 25.4))
    prefs.setValue('source_location', str(source))
    window = make_window(prefs)
    monkeypatch.setattr(window, '_layout_settings', lambda: LayoutSettings(
        dpi=25.4, number_images=False, cutter_mode='dual'))
    failures = []
    from automatic_print.ui import failure_dialog
    monkeypatch.setattr(failure_dialog, 'show_failure_dialog', lambda *args: failures.append(args[-1]))
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: None)
    monkeypatch.setattr(generation_actions.QDesktopServices, 'openUrl', lambda *args: True)
    window.generate()
    deadline = monotonic()+5
    while window.thread is not None:
        assert monotonic() < deadline
        APP.processEvents()
        sleep(0.01)
    assert not failures
    job = Path(window.job_path.text())
    assert job == source.parent / '切膜机文件'
    assert job != source
    assert 'JOB_' not in job.name
    assert all(path.name.startswith('batch123_') for path in job.rglob('*.png'))
    assert list((job/'常规').glob('*.png'))
    assert not list(job.glob('*.json'))
    assert list((source.parent/'排版日志').glob('*_排版报告*.txt'))
    assert image.is_file()
    assert not list(source.glob('JOB_*'))
    window.close()

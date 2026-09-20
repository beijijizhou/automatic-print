import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

from automatic_print.ui.main_window import MainWindow
from automatic_print.ui.settings_reset import reset_settings

APP = QApplication.instance() or QApplication([])
OWNERS = []


def test_reset_clears_residual_parameters_without_autosave_restoring_them(tmp_path, monkeypatch):
    import automatic_print.ui.settings_reset as settings_reset
    prefs = QSettings(str(tmp_path/'settings.ini'), QSettings.IniFormat)
    for key, value in {'output/parts': 8, 'output/save_workers': 8,
                       'layout/spacing_mm': 19, 'layout/manual_rotations': '{}',
                       'label/text_template': 'OLD', 'cutter/compare_films': True,
                       'riin/left_mm': 30, 'erp/selected_client': 'existing'}.items():
        prefs.setValue(key, value)
    image = tmp_path/'source.png'
    report = tmp_path/'排版报告.txt'
    image.touch()
    report.touch()
    window = MainWindow(prefs)
    OWNERS.append(window)
    window.startup_update_timer.stop()
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, 'information', lambda *a: None)
    restarted = []
    monkeypatch.setattr(settings_reset, 'request_application_restart',
                        lambda target: restarted.append(target) or True)
    window.preference_autosave.schedule()
    assert reset_settings(window)
    assert restarted == [window]
    window.preference_autosave.flush()
    assert not prefs.contains('output/save_workers')
    assert not prefs.contains('layout/manual_rotations')
    assert prefs.value('erp/selected_client') == 'existing'
    assert image.exists() and report.exists()
    fresh = MainWindow(prefs)
    OWNERS.append(fresh)
    fresh.startup_update_timer.stop()
    settings = fresh._layout_settings()
    assert settings.output_parts == 1 and settings.save_parallelism == 4
    assert settings.spacing_mm == 8 and settings.riin_left_mm == 15
    assert settings.compare_film_sizes and not settings.cutter_rotation_zone
    assert settings.platform_name == '隆丰' and settings.machine_number == 'M1'
    fresh.close()


def test_reset_cancel_or_busy_preserves_parameters(tmp_path, monkeypatch):
    prefs = QSettings(str(tmp_path/'settings.ini'), QSettings.IniFormat)
    prefs.setValue('output/save_workers', 8)
    window = MainWindow(prefs)
    OWNERS.append(window)
    window.startup_update_timer.stop()
    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.No)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a: None)
    assert not reset_settings(window)
    assert prefs.value('output/save_workers', type=int) == 8
    window.thread = object()
    assert not reset_settings(window)
    assert prefs.value('output/save_workers', type=int) == 8
    window.thread = None
    window.close()


def test_save_parameters_returns_to_layout_without_restart(tmp_path, monkeypatch):
    prefs = QSettings(str(tmp_path/'save.ini'), QSettings.IniFormat)
    window = MainWindow(prefs)
    OWNERS.append(window)
    window.startup_update_timer.stop()
    monkeypatch.setattr(QMessageBox, 'information', lambda *a: None)
    window.settings_dialog.show()
    window.spacing.setValue(12)
    window.save_settings_button.click()
    assert not window.settings_dialog.isVisible()
    assert prefs.value('layout/spacing_mm', type=float) == 12
    assert window.centralWidget().isEnabled()
    window.close()

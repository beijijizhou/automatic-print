import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QFileDialog
from automatic_print.ui.main_window import MainWindow
from automatic_print.ui.bulk_film_analysis import BulkFilmAnalysisDialog
from automatic_print.ui.folder_dialog_paths import KEY, image_dialog_start

APP = QApplication.instance() or QApplication([])
OWNERS = []


def setup(tmp_path):
    parent = tmp_path/'batches'
    first, second = parent/'one', parent/'two'
    first.mkdir(parents=True)
    second.mkdir()
    prefs = QSettings(str(tmp_path/'prefs.ini'), QSettings.IniFormat)
    prefs.setValue('source_location', str(first))
    window = MainWindow(prefs)
    window.startup_update_timer.stop()
    dialog = BulkFilmAnalysisDialog(window)
    OWNERS.extend((window, dialog))
    return window, dialog, parent, first, second


def test_multiple_selection_uses_shared_start_and_keeps_production_source(tmp_path, monkeypatch):
    window, dialog, parent, first, second = setup(tmp_path)
    starts = []
    original = QFileDialog.setDirectory
    def set_directory(chooser, value):
        starts.append(value)
        return original(chooser, value)
    monkeypatch.setattr(QFileDialog, 'setDirectory', set_directory)
    monkeypatch.setattr(QFileDialog, 'exec', lambda *_a: 1)
    monkeypatch.setattr(QFileDialog, 'selectedFiles', lambda *_a: [str(first), str(second)])
    dialog.choose()
    assert starts == [str(first)]
    assert dialog.folders.count() == 2
    assert window.folder.text() == str(first)
    assert window.preferences.value('source_location') == str(first)
    assert image_dialog_start(window) == str(parent)
    calls = []
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_a: calls.append(_a[2]) or '')
    assert not window.choose_folder()
    assert calls == [str(parent)]
    window.close()


def test_upper_directory_remembers_location_and_ignores_output_container(tmp_path, monkeypatch):
    window, dialog, parent, first, second = setup(tmp_path)
    (parent/'切膜机文件').mkdir()
    calls = []
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_a: calls.append(_a[2]) or str(parent))
    dialog.choose_parent()
    assert calls == [str(first)] and dialog.folders.count() == 2
    assert image_dialog_start(window) == str(parent)
    assert window.folder.text() == str(first)
    window.close()
    restored = MainWindow(QSettings(str(tmp_path/'prefs.ini'), QSettings.IniFormat))
    OWNERS.append(restored)
    restored.startup_update_timer.stop()
    assert image_dialog_start(restored) == str(parent)
    restored.close()


def test_single_choice_updates_shared_start_and_cancel_does_not(tmp_path, monkeypatch):
    window, dialog, parent, first, second = setup(tmp_path)
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_a: str(second))
    assert window.choose_folder()
    assert image_dialog_start(window) == str(second)
    monkeypatch.setattr(QFileDialog, 'exec', lambda *_a: 0)
    dialog.choose()
    assert image_dialog_start(window) == str(second)
    window.preferences.setValue(KEY, str(tmp_path/'missing'))
    assert image_dialog_start(window) == str(second)
    window.close()

import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QFileDialog
from automatic_print.ui.main_window import MainWindow
from automatic_print.ui.bulk_film_analysis import BulkFilmAnalysisDialog
from automatic_print.ui.cold_batch_benchmark import ColdBatchBenchmarkDialog
from automatic_print.ui import folder_dialog_paths
from automatic_print.ui.folder_dialog_paths import KEY, image_dialog_start

APP = QApplication.instance() or QApplication([])
OWNERS = []


def test_dtf_share_is_default_browse_location_without_selecting_a_source(tmp_path, monkeypatch):
    assert folder_dialog_paths.DEFAULT_DTF_SHARE == Path(r'\\192.168.11.28\dtf')
    share = tmp_path/'dtf'
    share.mkdir()
    monkeypatch.setattr(folder_dialog_paths, 'DEFAULT_DTF_SHARE', share)
    window = MainWindow(QSettings(str(tmp_path/'fresh.ini'), QSettings.IniFormat))
    window.startup_update_timer.stop()
    OWNERS.append(window)
    window.settings_dialog.show()
    window.print_settings_tabs.setCurrentIndex(3)
    APP.processEvents()
    assert window.folder.isVisible()
    assert window.folder.text() == ''
    assert image_dialog_start(window) == str(share)
    assert window.folder.placeholderText().endswith(str(share))
    starts = []
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory',
                        lambda *_args: starts.append(_args[2]) or '')
    assert not window.choose_folder()
    assert starts == [str(share)]
    assert window.folder.text() == ''
    window.close()


def test_cold_batch_benchmark_defaults_to_unc_share(tmp_path):
    window = MainWindow(QSettings(str(tmp_path/'cold.ini'), QSettings.IniFormat))
    window.startup_update_timer.stop()
    dialog = ColdBatchBenchmarkDialog(window)
    OWNERS.extend((window, dialog))
    assert Path(dialog.root.text()) == folder_dialog_paths.DEFAULT_DTF_SHARE
    dialog.close()
    window.close()


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
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory',
                        lambda *_a: starts.append(_a[2]) or str(parent))
    dialog.choose_parent()
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
    assert not hasattr(dialog, 'add') and not hasattr(dialog, 'choose')
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
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_a: '')
    dialog.choose_parent()
    assert image_dialog_start(window) == str(second)
    window.preferences.setValue(KEY, str(tmp_path/'missing'))
    assert image_dialog_start(window) == str(second)
    window.close()


def test_layout_entry_passes_checked_batch_scan_and_honors_cancel(tmp_path, monkeypatch):
    window, dialog, parent, first, second = setup(tmp_path)
    scan = {'batches': [{'folder': first, 'images': [], 'image_count': 0}],
            'errors': [], 'directories': 2, 'platform': ''}
    starts = []
    monkeypatch.setattr(window, 'choose_folder', lambda: True)
    monkeypatch.setattr(
        'automatic_print.ui.batch_folder_selection.choose_batch_folders',
        lambda *_args: scan)
    monkeypatch.setattr(
        'automatic_print.ui.bulk_workbench.start_bulk',
        lambda owner, root, prepared: starts.append((owner, root, prepared)))
    window.choose_and_generate()
    assert starts == [(window, str(first), scan)]
    monkeypatch.setattr(
        'automatic_print.ui.batch_folder_selection.choose_batch_folders',
        lambda *_args: None)
    window.choose_and_generate()
    assert len(starts) == 1
    assert window.status.text() == '已取消排版，文件夹选择保持不变。'
    window.close()

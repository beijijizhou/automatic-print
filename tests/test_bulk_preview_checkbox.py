from dataclasses import replace
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog
from automatic_print.ui.bulk_generation_worker import BulkGenerationWorker
from test_parallel_film_geometry import qr_sources, settings
from test_developer_mode import window, APP


def test_bulk_preview_keeps_every_batch_without_any_output(tmp_path, monkeypatch):
    folders = []
    for name in ('one', 'two', 'three'):
        folder = tmp_path/name
        folder.mkdir()
        qr_sources(folder)
        folders.append(folder)
    monkeypatch.setattr('automatic_print.ui.workers.GenerateWorker._save_history', lambda *_: None)
    config = replace(settings(), compare_film_sizes=False)
    worker = BulkGenerationWorker(folders, config, 2, preview_only=True)
    results, previews = [], []
    worker.finished.connect(results.append, Qt.DirectConnection)
    worker.preview.connect(lambda index, data: previews.append(index), Qt.DirectConnection)
    worker.run()
    assert set(previews) == {0, 1, 2}
    assert len(results[0]['records']) == 3 and not results[0]['errors']
    assert all(r['result']['preview_only'] and not r['output'] for r in results[0]['records'])
    assert not (tmp_path/'切膜机文件').exists()
    assert not list(tmp_path.rglob('manifest.json'))


def test_main_bulk_checkbox_runs_without_another_window(tmp_path, monkeypatch):
    folder = tmp_path/'batch'
    folder.mkdir()
    qr_sources(folder)
    second = tmp_path/'batch-two'
    second.mkdir()
    qr_sources(second)
    owner = window(tmp_path/'prefs.ini')
    owner.automation_home.preview_only.setChecked(True)
    monkeypatch.setattr(owner, '_layout_settings', lambda: replace(settings(), compare_film_sizes=False))
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: str(tmp_path))
    monkeypatch.setattr('automatic_print.ui.workers.GenerateWorker._save_history', lambda *_: None)
    owner.automation_home.start_layout_button.click()
    from time import monotonic
    deadline = monotonic()+15
    while owner.has_active_tasks() and monotonic() < deadline:
        APP.processEvents()
    assert not owner.has_active_tasks()
    assert owner.bulk_controller.worker is None
    assert len(owner.bulk_controller.records) == 2
    assert len(owner.automation_home.label_quick_panel.preview.planned) == 12
    assert not (tmp_path/'切膜机文件').exists()
    assert not hasattr(owner.automation_home.label_quick_panel.details_dialog, 'production_bulk_dialog')
    controller = owner.bulk_controller
    panel = owner.automation_home.label_quick_panel
    controller.selector.setCurrentIndex(1)
    APP.processEvents()
    assert all(path.parent == second for path, _ in panel.preview.planned)
    assert second.name in panel.summary.info.text()
    assert str(second) in panel.selected_source.text()
    assert '当前批次' in panel.selected_source.text()
    assert second.name in panel.selected_source.text()
    controller.selector.setCurrentIndex(0)
    APP.processEvents()
    assert all(path.parent == folder for path, _ in panel.preview.planned)
    assert panel.timings.data['status'] == '已完成'
    assert owner.grab().save(str(tmp_path/'unified-bulk.png'))
    owner.close()


def test_unified_action_accepts_a_single_batch_folder(tmp_path, monkeypatch):
    folder = tmp_path/'only-batch'
    folder.mkdir()
    qr_sources(folder)
    owner = window(tmp_path/'single.ini')
    owner.automation_home.preview_only.setChecked(True)
    monkeypatch.setattr(owner, '_layout_settings',
                        lambda: replace(settings(), compare_film_sizes=False))
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: str(folder))
    monkeypatch.setattr('automatic_print.ui.workers.GenerateWorker._save_history', lambda *_: None)
    owner.automation_home.start_layout_button.click()
    from time import monotonic
    deadline = monotonic()+15
    while owner.has_active_tasks() and monotonic() < deadline:
        APP.processEvents()
    assert not owner.has_active_tasks()
    assert len(owner.bulk_controller.records) == 1
    record = owner.bulk_controller.records[0]
    assert record['folder'] == str(folder)
    assert record['result']['preview_only']
    assert len(owner.automation_home.label_quick_panel.preview.planned) == 12
    owner.close()

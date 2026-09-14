import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from dataclasses import replace
import json
import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import Qt
from automatic_print.ui.bulk_generation_worker import BulkGenerationWorker
from test_parallel_film_geometry import qr_sources, settings


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
def test_normal_bulk_generates_independent_complete_batches(tmp_path, monkeypatch, engine):
    inputs = []
    for name in ('batch1', 'batch2', 'batch3'):
        folder = tmp_path/name
        folder.mkdir()
        qr_sources(folder)
        inputs.append(folder)
    config = replace(settings(), png_engine=engine, compare_reference_films=False,
                     compare_film_sizes=False)
    worker = BulkGenerationWorker(inputs, config, 2)
    monkeypatch.setattr('automatic_print.ui.workers.GenerateWorker._save_history', lambda *_: None)
    results, previews = [], []
    worker.finished.connect(results.append, Qt.DirectConnection)
    worker.preview.connect(lambda index, data: previews.append(index), Qt.DirectConnection)
    worker.run()
    result = results[0]
    assert result['actual_parallelism'] == 2 and not result['errors']
    assert len(result['records']) == 3 and set(previews) == {0, 1, 2}
    assert worker.settings.save_parallelism == 1
    for record in result['records']:
        output, folder, data = Path(record['output']), Path(record['folder']), record['result']
        assert output.parent == tmp_path/'切膜机文件'
        assert folder.name in output.name and folder.name in data['filename']
        assert (output/'排版报告.txt').is_file()
        assert json.loads((output/'manifest.json').read_text())['source_count'] == 12
        assert data['order_check'] and data['cut_corridor']['pixel_verified']
        with Image.open(output/data['filename']) as image:
            for p in data['placements']:
                with Image.open(folder/p['source']) as source:
                    original = np.asarray(source.rotate(p['rotation_degrees'], expand=True))
                rendered = np.asarray(image.crop((p['x_px'], p['y_px'],
                    p['x_px']+original.shape[1], p['y_px']+original.shape[0])))
                mask = original[:, :, 3] > 0
                assert np.array_equal(rendered[mask], original[mask])


def test_normal_entry_and_active_task_protection(tmp_path):
    from test_developer_mode import window, APP, OWNERS
    owner = window(tmp_path/'prefs.ini')
    panel = owner.automation_home.label_quick_panel
    assert not owner.developer_mode_enabled
    assert panel.bulk_generation_button.isVisible()
    panel.bulk_generation_button.click()
    APP.processEvents()
    dialog = panel.details_dialog.production_bulk_dialog
    OWNERS.append(dialog)
    assert dialog.isVisible() and '独立生成' in dialog.windowTitle()
    assert dialog.parallelism.value() == 4
    folder = tmp_path/'preview-batch'
    folder.mkdir()
    paths = qr_sources(folder)
    from automatic_print.layout import generate_layout
    payloads = []
    generate_layout(paths, tmp_path/'unused', replace(settings(), compare_reference_films=False),
                    preview_only=True, plan_ready=payloads.append)
    dialog.add_folders([folder])
    dialog.receive_preview(0, payloads[0])
    assert len(dialog.preview.planned) == 12
    assert 'preview-batch' in dialog.preview.detail
    APP.processEvents()
    dialog.thread = object()
    assert owner.has_active_tasks()
    owner.close()
    assert owner.isVisible()
    dialog.thread = None
    assert dialog.grab().save(str(tmp_path/'bulk-generation.png'))
    dialog.close()
    owner.close()

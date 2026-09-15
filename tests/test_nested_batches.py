from dataclasses import replace
from pathlib import Path
from threading import get_ident

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog

from automatic_print.layout_engine.batch_discovery import scan_batches
from automatic_print.ui.bulk_generation_worker import BulkGenerationWorker
from automatic_print.ui.batch_status_board import BatchStatusBoard
from test_parallel_film_geometry import qr_sources, settings
from test_developer_mode import window, APP


def tree(root):
    folders = [root, root/'白色'/'批次A', root/'黑色'/'大码'/'批次A']
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)
        qr_sources(folder)
    (root/'空目录').mkdir()
    old = root/'黑色'/'切膜机文件'
    old.mkdir()
    qr_sources(old)
    return folders


def test_scan_lists_direct_images_once_and_skips_outputs_and_symlink_loops(tmp_path):
    root = tmp_path/'HL'
    folders = tree(root)
    (root/'loop').symlink_to(root, target_is_directory=True)
    scan = scan_batches(root)
    assert {b['folder'] for b in scan['batches']} == set(folders)
    assert all(b['image_count'] == 12 and len(b['images']) == 12 for b in scan['batches'])
    assert len({p for b in scan['batches'] for p in b['images']}) == 36
    board = BatchStatusBoard()
    ordered = [b['folder'] for b in scan['batches']]
    board.reset(ordered, root, dict(enumerate(scan['batches'])))
    assert {item.text(0) for item in board.items.values()} == {'HL', '白色/批次A', '黑色/大码/批次A'}
    assert all(item.text(2) == '12' for item in board.items.values())
    assert all('NO1-1.png' in item.toolTip(0) for item in board.items.values())
    board.close()


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
@pytest.mark.parametrize('custom', [False, True])
def test_nested_outputs_preserve_source_tree_and_do_not_merge_parent_images(tmp_path, monkeypatch, engine, custom):
    root = tmp_path/'HL'
    folders = tree(root)
    base = tmp_path/'custom' if custom else None
    if base:
        base.mkdir()
    config = replace(settings(), png_engine=engine, compare_film_sizes=False)
    worker = BulkGenerationWorker([], config, 2, base, source_root=root)
    monkeypatch.setattr('automatic_print.ui.workers.GenerateWorker._save_history', lambda *_: None)
    scans, results = [], []
    worker.discovered.connect(scans.append, Qt.DirectConnection)
    worker.finished.connect(results.append, Qt.DirectConnection)
    worker.run()
    assert len(scans[0]['batches']) == 3 and not results[0]['errors']
    assert {Path(r['folder']) for r in results[0]['records']} == set(folders)
    output_root = (base or tmp_path)/'切膜机文件'/'HL'
    for record in results[0]['records']:
        source, output = Path(record['folder']), Path(record['output'])
        assert output.parent == output_root/source.relative_to(root)
        assert record['result']['order_check'] and record['result']['cut_corridor']['pixel_verified']
        assert len(record['result']['placements']) == 12
        assert (output/record['result']['filename']).is_file()
        assert (output/'排版报告.txt').is_file()
        assert not (output/'批次未完成，禁止打印.txt').exists()


def test_s2b_size_batches_share_one_output_parent(tmp_path,monkeypatch):
    root=tmp_path/'S2B批次'
    folders=[]
    for name in ('S','M','3XL'):
        folder=root/name
        folder.mkdir(parents=True)
        qr_sources(folder)
        folders.append(folder)
    config=replace(settings(),platform_name='隆丰',png_engine='pillow',compare_film_sizes=False)
    worker=BulkGenerationWorker([],config,3,source_root=root)
    monkeypatch.setattr('automatic_print.ui.workers.GenerateWorker._save_history',lambda *_:None)
    results=[]
    worker.finished.connect(results.append,Qt.DirectConnection)
    worker.run()
    assert not results[0]['errors'] and len(results[0]['records'])==3
    assert worker.original_settings.platform_name=='S2B'
    output_root=tmp_path/'切膜机文件'/'S2B批次'
    outputs=[Path(record['output']) for record in results[0]['records']]
    assert all(output.parent==output_root for output in outputs)
    assert len({output.name for output in outputs})==3
    assert any('3XL' in output.name for output in outputs)
    for record,output in zip(results[0]['records'],outputs):
        assert (output/record['result']['filename']).is_file()
        assert (output/'排版报告.txt').is_file()


def test_nested_scan_off_gui_and_selected_file_information_before_preview(tmp_path, monkeypatch):
    root = tmp_path/'HL'
    tree(root)
    owner = window(tmp_path/'prefs.ini')
    owner.automation_home.preview_only.setChecked(True)
    monkeypatch.setattr(owner, '_layout_settings', lambda: replace(settings(), compare_film_sizes=False))
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: str(root))
    monkeypatch.setattr('automatic_print.ui.workers.GenerateWorker._save_history', lambda *_: None)
    import automatic_print.layout_engine.batch_discovery as discovery
    original, threads = discovery.scan_batches, []
    def scan(*a, **kw):
        threads.append(get_ident())
        return original(*a, **kw)
    monkeypatch.setattr(discovery, 'scan_batches', scan)
    owner.automation_home.label_quick_panel.bulk_generation_button.click()
    from time import monotonic
    deadline = monotonic()+15
    while owner.has_active_tasks() and monotonic() < deadline:
        APP.processEvents()
    assert threads and threads[0] != get_ident()
    assert len(owner.bulk_controller.records) == 3
    assert all(item.text(2) == '12' for item in owner.bulk_controller.selector.items.values())
    assert not (tmp_path/'切膜机文件').exists()
    owner.close()


def test_discovered_names_available_before_any_layout_payload(tmp_path):
    from automatic_print.ui.bulk_workbench import BulkWorkbench
    root = tmp_path/'HL'
    tree(root)
    owner = window(tmp_path/'prefs.ini')
    controller = BulkWorkbench(owner)
    controller.root = root
    controller.payloads, controller.records, controller.stages, controller.timing_data = {}, {}, {}, {}
    controller.discovered(scan_batches(root))
    panel = owner.automation_home.label_quick_panel
    assert panel.manual_rotation.images.count() == 12
    assert 'NO1-1.png' in panel.manual_rotation.images.itemText(0)
    assert not controller.payloads
    controller.selector.setCurrentIndex(2)
    assert panel.manual_rotation.images.count() == 12
    assert str(controller.folders[2]) in panel.summary.info.text()
    owner.close()


def test_unreadable_branch_does_not_block_other_batches_and_scan_can_cancel(tmp_path, monkeypatch):
    import automatic_print.layout_engine.batch_discovery as discovery
    from automatic_print.cancellation import Cancellation, TaskCancelled
    root = tmp_path/'HL'
    tree(root)
    original = discovery.scandir
    def entries(path):
        if path == root/'白色':
            raise PermissionError('cannot read branch')
        return original(path)
    monkeypatch.setattr(discovery, 'scandir', entries)
    scan = scan_batches(root)
    assert len(scan['batches']) == 2 and len(scan['errors']) == 1
    assert scan['errors'][0]['folder'] == str(root/'白色')
    cancellation = Cancellation()
    cancellation.request()
    with pytest.raises(TaskCancelled):
        scan_batches(root, cancellation=cancellation)

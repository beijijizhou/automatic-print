from dataclasses import replace
from pathlib import Path
from threading import get_ident

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog

from automatic_print.layout_engine.intake.discovery.batch_discovery import scan_batches
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
    try:
        (root/'loop').symlink_to(root, target_is_directory=True)
    except OSError as error:
        if getattr(error, 'winerror', None) != 1314:
            raise
        # Windows service accounts cannot create symlinks without the optional
        # privilege. The same scan assertions still cover direct-image and
        # generated-output filtering on that runner.
    scan = scan_batches(root)
    assert {b['folder'] for b in scan['batches']} == set(folders)
    assert all(b['image_count'] == 12 and len(b['images']) == 12 for b in scan['batches'])
    assert len({p for b in scan['batches'] for p in b['images']}) == 36
    board = BatchStatusBoard()
    ordered = [b['folder'] for b in scan['batches']]
    board.reset(ordered, root, dict(enumerate(scan['batches'])))
    assert {item.text(0) for item in board.items.values()} == {'HL', '白色/批次A', '黑色/大码/批次A'}
    assert all(item.text(1) == '12' for item in board.items.values())
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
    output_root = (base or tmp_path)/'切膜机文件'
    for record in results[0]['records']:
        source, output = Path(record['folder']), Path(record['output'])
        assert output == output_root
        assert record['result']['order_check'] and record['result']['cut_corridor']['pixel_verified']
        assert len(record['result']['placements']) == 12
        filename = record['result']['filename']
        assert (output/filename).is_file()
        assert list(((base or tmp_path)/'排版日志').glob(f'{Path(filename).stem}_排版报告*.txt'))
        assert not list(output.glob('*.json'))


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
    output_root=tmp_path/'切膜机文件'
    outputs=[Path(record['output']) for record in results[0]['records']]
    assert set(outputs)=={output_root}
    assert len({record['result']['filename'] for record in results[0]['records']})==3
    assert any('3XL' in record['result']['filename'] for record in results[0]['records'])
    for record,output in zip(results[0]['records'],outputs):
        filename=record['result']['filename']
        assert (output/filename).is_file()
        assert list((tmp_path/'排版日志').glob(f'{Path(filename).stem}_排版报告*.txt'))


def test_multiple_folders_can_be_planned_as_one_virtual_batch(tmp_path,monkeypatch):
    root=tmp_path/'HL'
    source_folders=[]
    for tag,name in (('A','S'),('B','M'),('C','L')):
        folder=root/name
        folder.mkdir(parents=True)
        qr_sources(folder)
        for path in folder.glob('*.png'):
            path.rename(path.with_name(tag+path.name))
        source_folders.append(folder)
    config=replace(settings(),png_engine='pillow',compare_film_sizes=False)
    worker=BulkGenerationWorker([],config,3,source_root=root,combine_batches=True)
    monkeypatch.setattr('automatic_print.ui.workers.GenerateWorker._save_history',lambda *_:None)
    scans,results,previews,stages,source_events=[],[],[],[],[]
    worker.discovered.connect(scans.append,Qt.DirectConnection)
    worker.finished.connect(results.append,Qt.DirectConnection)
    worker.preview.connect(lambda _index,payload:previews.append(payload),Qt.DirectConnection)
    worker.progress.connect(lambda _i,_f,stage,*_rest:stages.append(stage),Qt.DirectConnection)
    worker.source_progress.connect(lambda *event:source_events.append(event),Qt.DirectConnection)
    worker.run()
    assert scans[0]['combined_batch_count']==len(source_folders)
    assert len(scans[0]['batches'])==1
    assert scans[0]['batches'][0]['image_count']==36
    assert [b['folder'].name for b in scans[0]['batches'][0]['source_batches']]==['L','M','S']
    assert len(results[0]['records'])==1 and not results[0]['errors'],results[0]
    result=results[0]['records'][0]['result']
    assert result['analysis']['image_count']==36
    assert len(previews)==1 and len(previews[0]['planned'])==36
    assert any('测量标签与刀码 · 4线程并行'==stage for stage in stages)
    assert {event[1] for event in source_events}=={str(folder) for folder in source_folders}
    assert all(event[3]<=event[4] for event in source_events)
    output=Path(results[0]['records'][0]['output'])
    assert output==tmp_path/'切膜机文件'
    assert (output/result['filename']).is_file()
    assert list((tmp_path/'排版日志').glob(f"{Path(result['filename']).stem}_排版报告*.txt"))


def test_combined_status_keeps_child_folders_visible(tmp_path):
    root=tmp_path/'S2B'
    sources=[]
    for name,count in (('S',12),('M',8),('3XL',4)):
        folder=root/name
        folder.mkdir(parents=True)
        sources.append({'folder':folder,'images':[], 'image_count':count})
    combined={'folder':root,'images':[],'image_count':24,'source_batches':sources}
    board=BatchStatusBoard()
    board.reset([root],root,{0:combined})
    item=board.items[0]
    assert item.childCount()==3 and item.isExpanded()
    assert [item.child(i).text(0) for i in range(3)]==['S','M','3XL']
    assert [item.child(i).text(1) for i in range(3)]==['12','8','4']
    board.update_source(0,str(root/'S'),'测量标签与刀码 · 4线程并行',3,12,'S-003.png')
    assert item.child(0).toolTip(0).endswith('S-003.png') and '3/12' in item.child(0).toolTip(0)
    assert '已加入合并批次' in item.child(1).toolTip(0)
    board.update_batch(0,'膜规格比较',2,4)
    assert item.treeWidget() is board.groups['进行中'] and item.isExpanded()
    assert all('随整批处理' in item.child(i).toolTip(0) for i in range(3))
    board.update_batch(0,'批次生成完成')
    assert item.treeWidget() is board.groups['已完成'] and item.isExpanded()
    assert all('已随整批完成' in item.child(i).toolTip(0) for i in range(3))
    board.close()


def test_nested_scan_off_gui_and_selected_file_information_before_preview(tmp_path, monkeypatch):
    root = tmp_path/'HL'
    tree(root)
    owner = window(tmp_path/'prefs.ini')
    owner.automation_home.preview_only.setChecked(True)
    monkeypatch.setattr(owner, '_layout_settings', lambda: replace(settings(), compare_film_sizes=False))
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *_: str(root))
    monkeypatch.setattr('automatic_print.ui.workers.GenerateWorker._save_history', lambda *_: None)
    import automatic_print.layout_engine.intake.discovery.batch_discovery as discovery
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
    assert all(item.text(1) == '12' for item in owner.bulk_controller.selector.items.values())
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
    import automatic_print.layout_engine.intake.discovery.batch_discovery as discovery
    from automatic_print.runtime.cancellation import Cancellation, TaskCancelled
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

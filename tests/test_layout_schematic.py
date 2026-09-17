import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from automatic_print.layout_engine import LayoutSettings
from automatic_print.layout_engine.domain.models import Placement
from automatic_print.ui.layout_schematic import schematic_items
from automatic_print.ui.pair_preview import PairProductionPreview
from automatic_print.ui.previews.runtime.snapshot import install_snapshot


def test_schematic_labels_single_double_and_multi_order_groups():
    report = {'orders': [
        {'order': 'ONE', 'kind': '单件单面', 'sizes': {'S': 1},
         'items': [{'size': 'S', 'images': [{'path': '/batch/single.png'}]}]},
        {'order': 'TWO', 'kind': '单件双面', 'sizes': {'M': 1},
         'items': [{'size': 'M', 'images': [
             {'path': '/batch/front.png'}, {'path': '/batch/back.png'},
         ]}]},
        {'order': 'ORDER123', 'kind': '多件订单', 'sizes': {'S': 1, 'L': 2},
         'items': [
             {'size': 'S', 'images': [{'path': '/batch/a.png'}]},
             {'size': 'L', 'images': [{'path': '/batch/b.png'}, {'path': '/batch/c.png'}]},
         ]},
    ]}
    items = schematic_items(report)

    assert items['/batch/single.png']['title'] == 'S 尺码群'
    assert items['/batch/front.png']['title'] == '双面 M 尺码群'
    assert items['/batch/front.png']['detail'] == '正面'
    assert items['/batch/back.png']['detail'] == '背面'
    assert items['/batch/a.png']['title'] == '订单 ORDER123'
    assert '尺码群 S×1 · L×2' in items['/batch/a.png']['detail']


def test_whole_batch_schematic_never_decodes_visible_thumbnails(tmp_path):
    QApplication.instance() or QApplication([])
    for index, size in enumerate(('S', 'M')):
        Image.new('RGBA', (120, 180), 'blue').save(
            tmp_path/f'B{index}-1-T-Black-{size}-NO1-1.png', dpi=(25.4, 25.4)
        )
    preview = PairProductionPreview(lambda: LayoutSettings(
        dpi=25.4, allow_rotation=False, number_images=False,
        color_block_enabled=False,
    ))
    preview.overview = True
    paths = sorted(tmp_path.glob('*.png'))
    planned = [
        (path, Placement(
            path.name, index, (index-1)*140, 0, 120, 180,
            0, 0, 0, 0, 0, 140, 180,
        ))
        for index, path in enumerate(paths, 1)
    ]
    report = {'orders': [
        {'order': f'B{index}', 'kind': '单件单面', 'sizes': {size: 1},
         'items': [{'size': size, 'images': [{'path': str(path)}]}]}
        for index, (path, size) in enumerate(zip(paths, ('S', 'M')))
    ]}
    preview.batch_payload = {'planned': planned, 'analysis': report}
    install_snapshot(preview, planned, {}, preview.settings_getter())
    preview.detail = '整批轻量结构图'
    preview.resize(800, 500)
    rendered = QImage(preview.size(), QImage.Format_ARGB32)
    rendered.fill(0)
    preview.render(rendered)

    assert preview.images == {}
    assert preview.planned
    assert not rendered.isNull()
    assert '整批轻量结构图' in preview.detail
    assert rendered.save(str(tmp_path/'lightweight-layout.png'))
    preview.close()

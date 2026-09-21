import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from dataclasses import replace
from pathlib import Path

import numpy as np
from PIL import Image
import pytest
from PySide6.QtWidgets import QApplication

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.intake.metadata.image_anomalies import anomaly_text
from automatic_print.layout_engine.output.output_sizes import cutting_report
from automatic_print.layout_engine.domain.models import Placement
from automatic_print.layout_engine.cutting.geometry.printed_guides import collect_guides, dot_boxes
from automatic_print.layout_engine.cutting.validation.marked_pixel_validation import validate_marked_pillow
from automatic_print.layout_engine.cutting.validation.cut_validation import corridor_checks
from automatic_print.ui.batch_summary import BatchSummaryPanel
from tests.test_platform_labels import qr_image


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
@pytest.mark.parametrize('parts', [1, 3])
def test_missing_qr_keeps_whole_orders_and_actual_pixels(tmp_path, engine, parts):
    paths = []
    missing = []
    for order in range(3):
        for side in (1, 2):
            path = tmp_path/f'B{order}-1-T-Black-M-NO1-{side}.png'
            if side == 2:
                Image.new('RGBA', (180, 250), 'blue').save(path, dpi=(25.4, 25.4))
                missing.append(path.name)
            else:
                qr_image(path)
            paths.append(path)
    settings = LayoutSettings(dpi=25.4, cutter_mode='dual', cutter_auto_knife=True,
        cutter_rotation_zone=True, cutter_knife_dots=False,
        allow_rotation=False, platform_name='隆丰',
        output_parts=parts, save_parallelism=3, save_memory_unlimited=True,
        compare_film_sizes=True, png_engine=engine)
    result = generate_layout(paths, tmp_path/'out', settings)
    anomalies = result['analysis']['image_anomalies']
    assert {r['source'] for r in anomalies} == {path.name for path in paths}
    assert all('继续完成排版' in r['action'] for r in anomalies)
    assert all(any(r['source'] == name and '未找到可靠膜标签区域' in r['kind']
                   for r in anomalies)
               for name in missing)
    assert all(not r['error'] for r in result['analysis']['film_comparison']['rows'])
    assert all(name in cutting_report(result) for name in missing)
    all_sources = []
    for part in result.get('parts', [result]):
        assert part['order_check']
        placements = part['placements']
        all_sources += [p['source'] for p in placements]
        assert all(p['cut_zone'] != '旋转区' for p in placements)
        assert all(p['platform_width_px'] == 0 for p in placements if p['source'] in missing)
        planned = [(tmp_path/p['source'], Placement(**p)) for p in placements]
        spans, _ = collect_guides(planned, settings)
        with Image.open(tmp_path/'out'/part['filename']) as image:
            validate_marked_pillow(image, part['cut_corridor'], list(dot_boxes(spans, settings.dpi)),
                                   part['transition_marks'])
            for path, p in planned:
                with Image.open(path) as source:
                    original = np.asarray(source)
                actual = np.asarray(image.crop((p.x_px, p.y_px,
                                                p.x_px+p.width_px, p.y_px+p.height_px)))
                ink = original[:, :, 3] == 255
                for x, y, width, height in (
                    (p.platform_x_px, p.platform_y_px,
                     p.platform_width_px, p.platform_height_px),
                    (p.number_x_px, p.number_y_px,
                     p.number_width_px, p.number_height_px),
                ):
                    if width and height:
                        left, top = x-p.x_px, y-p.y_px
                        ink[max(0, top):top+height, max(0, left):left+width] = False
                if not np.array_equal(original[ink], actual[ink]):
                    raise AssertionError(
                        f'{path.name}: {original[2, 3].tolist()} -> '
                        f'{actual[2, 3].tolist()}')
    assert sorted(all_sources) == sorted(p.name for p in paths)
    for order in range(3):
        assert any(all(any(p['source'] == f'B{order}-1-T-Black-M-NO1-{side}.png'
                           for p in part['placements']) for side in (1, 2))
                   for part in result.get('parts', [result]))


def test_anomaly_names_visible_copyable_and_clear_on_next_job():
    app = QApplication.instance() or QApplication([])
    panel = BatchSummaryPanel()
    panel.show()
    data = {'batch_type': '测试', 'order_count': 1, 'piece_count': 1,
            'image_count': 1, 'double_pairs': 0,
            'image_anomalies': [{'source': '异常.png', 'kind': '二维码未识别', 'action': '原图保留'}]}
    panel.show_analysis(data)
    app.processEvents()
    assert panel.anomalies.isVisible()
    assert '异常.png' in panel.anomalies.text() == anomaly_text(data)
    panel.start('/tmp/new-job')
    assert not panel.anomalies.isVisible() and not panel.anomalies.text()
    panel.close()


def test_safe_right_pair_without_standalone_baseline_still_generates(tmp_path):
    paths = []
    for item, size in enumerate(((326, 150), (219, 500)), 1):
        path = tmp_path/f'B0-{item}-T-Black-M-NO1-1.png'
        Image.new('RGBA', size, 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    config = LayoutSettings(dpi=25.4, cutter_mode='dual', cutter_knife_mm=237,
                            allow_rotation=False, number_images=False)
    result = generate_layout(paths, tmp_path/'out', config)
    assert len(result['placements']) == 2
    assert result['cut_corridor']['pixel_verified']
    assert result['baseline_height_mm'] == result['height_mm']


def test_manual_rotation_without_qr_retains_safe_external_marks(tmp_path):
    path = tmp_path/'B0-1-T-Black-M-NO1-1.png'
    Image.new('RGBA', (180, 250), 'blue').save(path, dpi=(25.4, 25.4))
    config = LayoutSettings(dpi=25.4, cutter_mode='single', platform_name='隆丰',
        allow_rotation=False, manual_rotations=((str(path.resolve()), 90),))
    result = generate_layout([path], tmp_path/'out', config)
    p = result['placements'][0]
    assert p['rotation_degrees'] == 90 and p['platform_width_px'] == 0
    assert p['color_block_x_px'] == 0
    assert p['x_px'] >= p['color_block_width_px']
    assert result['analysis']['image_anomalies'][0]['source'] == path.name

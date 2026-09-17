from collections import defaultdict
from dataclasses import replace
from pathlib import Path
import pytest
from PIL import Image

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.cutting.validation.cut_validation import corridor_checks
from automatic_print.layout_engine.orders.order_groups import order_key


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
@pytest.mark.parametrize('parallel', [1, 2])
def test_segments_preserve_full_orders_pairing_and_real_pixels(tmp_path, engine, parallel):
    paths = []
    for order in range(8):
        for face in ((1, 2) if order % 3 == 0 else (1,)):
            path = tmp_path/f'B{order}-1-T-Black-M-NO1-{face}.png'
            Image.new('RGBA', (100, 140), 'blue').save(path, dpi=(25.4,25.4))
            paths.append(path)
    settings = LayoutSettings(dpi=25.4, margin_mm=3, media_width_mm=580,
        cutter_mode='dual', cutter_auto_knife=True, number_images=True,
        output_parts=3, save_parallelism=parallel, png_engine=engine)
    payloads = []
    result = generate_layout(paths, tmp_path/'out', settings, plan_ready=payloads.append, batch_name='批次123')
    assert len(payloads) == 1
    assert result['segment_count'] == 3
    assert result['actual_save_parallelism'] == parallel
    assert len(result['files']) == len(set(result['files'])) == 3
    assert all(name.startswith('批次123_') for name in result['files'])
    assert all('批次8单' in name for name in result['files'])
    membership = defaultdict(set)
    total_images = 0
    for part in result['parts']:
        orders = {order_key(Path(p['source'])) for p in part['placements']}
        assert f'本段{len(orders)}单' in part['filename']
        total_images += len(part['placements'])
        for p in part['placements']:
            membership[order_key(Path(p['source']))].add(part['filename'])
        assert part['cut_corridor']['pixel_verified']
        with Image.open(tmp_path/'out'/part['filename']) as image:
            for check in corridor_checks(part['cut_corridor']):
                stripe = image.crop((
                    check['safe_left_px'], check.get('start_y_px', 0),
                    check['safe_right_px'], check.get('end_y_px', image.height),
                ))
                assert stripe.getchannel('A').getextrema() == (0, 0)
            for p in part['placements']:
                assert image.getpixel((p['color_block_x_px'], p['color_block_y_px'])) == (255, 0, 0, 255)
    assert total_images == len(paths)
    assert all(len(files) == 1 for files in membership.values())
    assert len({p['cutter_knife_mm'] for p in result['parts']}) == 1


def test_one_large_order_cannot_be_split(tmp_path):
    paths = []
    for piece in range(1, 5):
        path = tmp_path/f'BORDER-{piece}-T-Black-L-NO{piece}-1.png'
        Image.new('RGBA', (100, 140), 'blue').save(path, dpi=(25.4,25.4))
        paths.append(path)
    result = generate_layout(paths, tmp_path/'out', LayoutSettings(dpi=25.4,
        cutter_mode='dual', output_parts=4, number_images=False))
    assert result['segment_count'] == 1
    assert len(result['parts'][0]['placements']) == 4
    assert '批次1单 4件 本段1单 4件' in result['filename']


def test_partial_segment_failure_quarantines_only_new_files(tmp_path, monkeypatch):
    from automatic_print.layout_engine.pipeline import service
    paths = []
    for i in range(4):
        path = tmp_path/f'B{i}-1-T-Black-M-NO1-1.png'
        Image.new('RGBA', (100, 140), 'blue').save(path, dpi=(25.4,25.4))
        paths.append(path)
    output = tmp_path/'out'
    output.mkdir()
    old = output/'old.png'
    old.write_bytes(b'old output')
    original = service.generate_layout
    def fail_second(*args, **kwargs):
        if kwargs.get('filename_suffix') == ' 第002段':
            raise RuntimeError('test save failure')
        return original(*args, **kwargs)
    monkeypatch.setattr(service, 'generate_layout', fail_second)
    with pytest.raises(RuntimeError, match='test save failure'):
        original(paths, output, LayoutSettings(dpi=25.4, cutter_mode='dual',
            output_parts=2, save_parallelism=1, number_images=False))
    assert list(output.glob('*.png')) == [old]
    assert old.read_bytes() == b'old output'
    assert list(output.glob('*.生成未完成'))

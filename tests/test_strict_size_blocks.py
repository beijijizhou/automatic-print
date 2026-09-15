from dataclasses import replace
from itertools import groupby
from PIL import Image
import pytest
from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.size_policy import validate_single_size_blocks
from automatic_print.layout_engine.source_metadata import source_size


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
@pytest.mark.parametrize('rotations', [False, True])
def test_shuffled_small_and_double_single_orders_stay_in_size_blocks(tmp_path, engine, rotations):
    paths = []
    for i, size in enumerate(('XL','S','M','S','XL','M','XXL','2XL','S','M','XL','2XL')):
        for face in ((1, 2) if i in (1, 4) else (1,)):
            path = tmp_path/f'B{i}-1-T-Black-{size}-NO1-{face}.png'
            width, height = (100, 150) if i % 3 == 0 else (180, 240)
            Image.new('RGBA', (width, height), 'blue').save(path, dpi=(25.4,25.4))
            paths.append(path)
    settings = LayoutSettings(media_width_mm=580, dpi=25.4, number_images=False,
        cutter_mode='dual', cutter_auto_knife=True, cutter_rotation_zone=rotations,
        png_engine=engine, margin_mm=0)
    result = generate_layout(paths, tmp_path/'out', settings)
    placements = result['placements']
    ordered = sorted(placements, key=lambda p: (p['row_y_px'], p['x_px']))
    sizes = [source_size(next(path for path in paths if path.name == p['source'])) for p in ordered]
    assert [size for size, _group in groupby(sizes)] == ['S','M','XL','2XL']
    assert result['order_check']['single_size_verified']
    assert result['order_check']['double_pairs'] == 2
    assert result['cut_corridor']['pixel_verified']
    with Image.open(tmp_path/'out'/result['filename']) as image:
        checks = result['cut_corridor'].get('zones', [result['cut_corridor']])
        for check in checks:
            crop = (check['safe_left_px'], check.get('start_y_px', 0),
                    check['safe_right_px'], check.get('end_y_px', image.height))
            assert image.getchannel('A').crop(crop).getextrema() == (0, 0)


def test_independent_check_rejects_size_interleaving(tmp_path):
    paths = []
    for i, size in enumerate(('S','S','M')):
        path = tmp_path/f'B{i}-1-T-Black-{size}-NO1-1.png'
        Image.new('RGBA', (180, 240), 'blue').save(path, dpi=(25.4,25.4))
        paths.append(path)
    payloads = []
    generate_layout(paths, tmp_path/'out', LayoutSettings(media_width_mm=580,
        dpi=25.4, cutter_mode='dual', cutter_auto_knife=True, number_images=False),
        plan_ready=payloads.append)
    planned = payloads[0]['planned']
    by_path = dict(planned)
    broken = [(path, replace(by_path[path], row_y_px=i*300, cut_zone='双排区'))
              for i, path in enumerate((paths[0], paths[2], paths[1]))]
    with pytest.raises(ValueError, match='尺码从小到大'):
        validate_single_size_blocks(paths, broken)

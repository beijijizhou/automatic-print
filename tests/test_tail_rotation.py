from dataclasses import replace
from PIL import Image
import pytest

from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.planner import plan_layout


def make_sources(tmp_path, rows):
    paths = []
    for index, (size, width, height, faces) in enumerate(rows):
        for face in faces:
            path = tmp_path/f'B{index}-1-T-Black-{size}-NO1-{face}.png'
            Image.new('RGBA', (width, height), 'blue').save(path, dpi=(25.4, 25.4))
            paths.append(path)
    return paths


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
def test_fast_tail_rotation_keeps_full_sizes_double_faces_and_real_cut_channels(tmp_path, engine):
    paths = make_sources(tmp_path, [('S', 150, 180, (1,)), ('S', 150, 180, (1,)),
        ('3XL', 340, 500, (1, 2)), ('4XL', 355, 520, (1,)), ('5XL', 360, 540, (1,))])
    settings = LayoutSettings(dpi=25.4, media_width_mm=580, cutter_mode='dual',
        cutter_auto_knife=True, cutter_tail_rotation=True, rotation_marker_shift_mm=2,
        transition_lines=True, png_engine=engine)
    original = plan_layout(paths, replace(settings, cutter_tail_rotation=False), None)
    stages = []
    result = generate_layout(paths, tmp_path/'out', settings,
        progress=lambda stage, current, total, filename: stages.append(stage))
    assert result['height_px'] < original[3]
    assert '比较末尾旋转' in stages
    assert '比较旋转区域' not in stages
    assert result['order_check']['single_size_blocks'] == ['S', '3XL', '4XL', '5XL']
    assert result['size_range'] == 'S+3XL-5XL'
    assert result['size_range'] in result['filename']
    rotated = [p for p in result['placements'] if p['cut_zone'] == '旋转区']
    assert len(rotated) == 4
    assert all(p['rotation_degrees'] == 90 and p['color_block_x_px'] == 0 for p in rotated)
    assert rotated[0]['source'].endswith('NO1-1.png') and rotated[1]['source'].endswith('NO1-2.png')
    assert rotated[1]['row_y_px'] == (rotated[0]['row_y_px']+
                                      rotated[0]['footprint_height_px']+
                                      settings.spacing_mm)
    with Image.open(tmp_path/'out'/result['filename']) as image:
        for zone in result['cut_corridor']['zones']:
            stripe = image.crop((zone['safe_left_px'], zone['start_y_px'], zone['safe_right_px'], zone['end_y_px']))
            assert stripe.getchannel('A').getextrema() == (0, 0)
            assert zone['pixel_verified']
        for r in result['transition_marks']:
            assert image.getpixel((image.width//2, r['y'])) == (255, 0, 0, 255)


def test_fast_tail_does_not_rotate_when_not_saving_or_unknown_orders(tmp_path):
    paths = make_sources(tmp_path, [('3XL', 280, 400, (1,)), ('3XL', 280, 400, (1,))])
    settings = LayoutSettings(dpi=25.4, cutter_mode='dual', cutter_auto_knife=True,
        cutter_tail_rotation=True, number_images=False)
    original = plan_layout(paths, replace(settings, cutter_tail_rotation=False), None)
    assert plan_layout(paths, settings, None) == original
    extra = tmp_path/'unknown.png'
    Image.new('RGBA', (50, 60), 'blue').save(extra, dpi=(25.4, 25.4))
    result = plan_layout(paths+[extra], settings, None)
    assert not any(p.cut_zone for _, p in result[0])

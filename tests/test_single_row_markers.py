from dataclasses import replace

from PIL import Image
import pytest

from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.cut_validation import corridor_checks, validate_cut_corridor


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
@pytest.mark.parametrize('mode', ['single', 'dual'])
def test_all_single_rows_have_left_edge_marker_in_saved_png(tmp_path, engine, mode):
    paths = []
    # Different sizes cannot share a row; a large image previously used right only.
    for i, (size, width) in enumerate(zip(('S', 'M', 'L', 'XL', '2XL'), (90, 320, 100, 330, 110))):
        path = tmp_path / f'B{i}-1-T-Black-{size}-NO1-1.png'
        Image.new('RGBA', (width, 180), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    settings = LayoutSettings(media_width_mm=580, dpi=25.4, margin_mm=0,
        cutter_mode=mode, cutter_knife_mm=180, cutter_auto_knife=True,
        png_engine=engine, label_text_template='CY26 M1')
    payloads = []
    result = generate_layout(paths, tmp_path/'out', settings, plan_ready=payloads.append)
    assert len(result['placements']) == len(paths)
    assert result['order_check']['single_size_verified']
    assert all(p.color_block_x_px == 0 for _, p in payloads[0]['planned'])
    with Image.open(tmp_path/'out'/result['filename']) as image:
        for p in result['placements']:
            assert p['color_block_x_px'] == 0
            assert p['number_x_px'] == 0
            assert image.convert('RGBA').getpixel((0, p['color_block_y_px'])) == (255, 0, 0, 255)
        if mode == 'dual':
            check = result['cut_corridor']
            assert check['pixel_verified']
            for corridor in corridor_checks(check):
                stripe = image.crop((
                    corridor['safe_left_px'], corridor.get('start_y_px', 0),
                    corridor['safe_right_px'], corridor.get('end_y_px', image.height),
                ))
                assert stripe.getchannel('A').getextrema() == (0, 0)


def test_manual_knife_recovers_single_image_without_right_only_marker(tmp_path):
    path = tmp_path/'B1-1-T-Black-L-NO1-1.png'
    Image.new('RGBA', (320, 180), 'blue').save(path, dpi=(25.4, 25.4))
    settings = LayoutSettings(media_width_mm=580, dpi=25.4, cutter_mode='dual',
        cutter_knife_mm=180, number_images=False)
    result = generate_layout([path], tmp_path/'out', settings)
    assert len(result['placements']) == 1
    placement = result['placements'][0]
    assert placement['rotation_degrees'] == 90
    assert placement['color_block_x_px'] == 0


def test_independent_check_rejects_right_only_row(tmp_path):
    path = tmp_path/'B1-1-T-Black-L-NO1-1.png'
    Image.new('RGBA', (100, 180), 'blue').save(path, dpi=(25.4, 25.4))
    settings = LayoutSettings(media_width_mm=580, dpi=25.4, cutter_mode='dual',
        cutter_knife_mm=290, number_images=False)
    payloads = []
    generate_layout([path], tmp_path/'out', settings, plan_ready=payloads.append)
    _, p = payloads[0]['planned'][0]
    broken = replace(p, x_px=p.x_px+293, color_block_x_px=293)
    with pytest.raises(ValueError, match='单排色块'):
        validate_cut_corridor([(path, broken)], settings, 580)
    with pytest.raises(ValueError, match='单排色块'):
        validate_cut_corridor([(path, broken)], replace(settings, cutter_mode='single'), 580)

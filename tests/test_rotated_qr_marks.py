from dataclasses import replace

import numpy as np
from PIL import Image
import pytest

from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.cut_guide_geometry import detect_guide_band
from automatic_print.layout_engine.item_factory import read_items
from automatic_print.layout_engine.transition_marks import rotation_marker_item


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
@pytest.mark.parametrize('parts', [1, 3])
def test_rotated_whole_batch_qr_label_and_fixed_marker(tmp_path, engine, parts):
    cv2 = pytest.importorskip('cv2')
    qr = Image.fromarray(cv2.QRCodeEncoder_create().encode('ROTATED123')).convert('RGBA')
    paths = []
    for index in range(12):
        rotated = Image.new('RGBA', (250, 300))
        rotated.paste('white', (35, 10, 100, 55))
        rotated.paste(qr, (45, 20))
        rotated.paste('blue', (115, 0, 250, 300))
        path = tmp_path/f'B{index//2}-1-T-Black-M-NO1-{index%2+1}.png'
        rotated.rotate(-90, expand=True).save(path, dpi=(25.4, 25.4))
        paths.append(path)
        assert detect_guide_band(path) is not None
    settings = LayoutSettings(dpi=25.4, media_width_mm=580, margin_mm=0,
        cutter_mode='single', allow_rotation=False, platform_name='隆丰',
        platform_font_height_mm=6, label_text_template='CY 1001Mt26',
        label_machine_enabled=True, label_sequence_enabled=True,
        manual_rotations=tuple((str(p.resolve()), 90) for p in paths),
        png_engine=engine, output_parts=parts, save_memory_unlimited=True)
    previews = []
    result = generate_layout(paths, tmp_path/'out', settings, plan_ready=previews.append)
    assert len(previews[0]['planned']) == 12
    from automatic_print.layout_engine.marker_space import validate_embedded_marks
    path, placement = previews[0]['planned'][0]
    with pytest.raises(ValueError, match='未与二维码同高'):
        validate_embedded_marks([(path, replace(placement,
            color_block_y_px=placement.color_block_y_px+1))])
    with pytest.raises(ValueError, match='未放在二维码下方'):
        validate_embedded_marks([(path, replace(placement,
            number_x_px=placement.number_x_px+1))])
    for part in result.get('parts', [result]):
        with Image.open(tmp_path/'out'/part['filename']) as output:
            for p in part['placements']:
                path = tmp_path/p['source']
                band = detect_guide_band(path).rotated(90)
                assert p['color_block_x_px'] == 0
                assert p['color_block_y_px'] == p['y_px']+round(band.top*p['height_px'])
                assert p['number_x_px'] == p['x_px']+round(band.left*p['width_px'])
                assert p['number_y_px'] >= p['y_px']+band.bottom*p['height_px']
                assert p['number_y_px']+p['number_height_px'] <= p['y_px']+p['height_px']
                assert output.getpixel((0, p['color_block_y_px'])) == (255, 0, 0, 255)
                with Image.open(path) as source:
                    original = np.asarray(source.rotate(90, expand=True))
                cropped = np.asarray(output.crop((p['x_px'], p['y_px'],
                    p['x_px']+p['width_px'], p['y_px']+p['height_px'])))
                ink = original[:, :, 3] > 0
                assert np.array_equal(original[ink], cropped[ink])
    choices, _ = read_items(paths, settings, None)
    item = choices[0][0]
    shifted = rotation_marker_item(item, replace(settings, rotation_marker_shift_mm=2))
    assert shifted.block_rx == item.block_rx+2
    assert shifted.label_rx == item.label_rx
    if parts == 1:
        from automatic_print.layout_engine.rotation_zones import _rotated
        from automatic_print.layout_engine.service import generate_layout as save_plan
        from automatic_print.layout_engine.batch_analysis import analyze_batch
        zone_settings = replace(settings, cutter_mode='dual', output_parts=1,
            cutter_rotation_zone=True, transition_lines=True, rotation_marker_shift_mm=2)
        planned, labels, height, knife = _rotated(paths, zone_settings)
        planned = [(path, replace(p, cut_zone='旋转区', cut_knife_x_px=knife))
                   for path, p in planned]
        zone = save_plan(paths, tmp_path/'zone', zone_settings, prepared_plan={
            'plan': (planned, labels, 580, height, height), 'settings': zone_settings,
            'analysis': analyze_batch(paths, zone_settings)})
        assert zone['cut_corridor']['pixel_verified']
        with Image.open(tmp_path/'zone'/zone['filename']) as output:
            for p in zone['placements']:
                assert p['color_block_x_px'] == 2
                assert p['number_x_px'] > 2
                assert output.getpixel((2, p['color_block_y_px'])) == (255, 0, 0, 255)
                with Image.open(tmp_path/p['source']) as source:
                    original = np.asarray(source.rotate(90, expand=True))
                crop = np.asarray(output.crop((p['x_px'], p['y_px'],
                    p['x_px']+p['width_px'], p['y_px']+p['height_px'])))
                ink = original[:, :, 3] > 0
                assert np.array_equal(original[ink], crop[ink])

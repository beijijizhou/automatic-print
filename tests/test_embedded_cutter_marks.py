from dataclasses import replace
from math import ceil, floor
import numpy as np
from PIL import Image
import pytest

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.labeling.markers.marker_space import validate_embedded_marks
from automatic_print.layout_engine.cutting.geometry.cut_guide_geometry import detect_guide_band


def make_batch(tmp_path):
    cv2 = pytest.importorskip('cv2')
    qr = Image.fromarray(cv2.QRCodeEncoder_create().encode('TEST123')).convert('RGBA')
    paths = []
    for index in range(16):
        path = tmp_path/f'B{index}-1-T-Black-M-NO1-1.png'
        width = 280 if index < 12 else 200
        image = Image.new('RGBA', (width, 250))
        x = width-110 if index < 12 else 0
        image.paste('white', (x, 0, x+110, 60))
        image.paste(qr, (x+75, 10))
        image.paste('blue', (0, 70, width, 250))
        image.save(path, dpi=(25.4, 25.4))
        paths.append(path)
    return paths


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
@pytest.mark.parametrize('parts', [1, 2])
def test_mixed_full_batch_embeds_without_covering_any_original_ink(tmp_path, engine, parts):
    paths = make_batch(tmp_path)
    settings = LayoutSettings(dpi=25.4, media_width_mm=580, margin_mm=0,
        cutter_mode='dual', cutter_auto_knife=True, allow_rotation=False,
        platform_name='隆丰', platform_font_height_mm=6,
        label_text_template='CY 1001Mt26', label_machine_enabled=True,
        label_sequence_enabled=True, label_position='block_below',
        png_engine=engine, output_parts=parts, save_memory_unlimited=True)
    payloads = []
    result = generate_layout(paths, tmp_path/'out', settings, plan_ready=payloads.append)
    # Text faces inward from either card edge and adds no horizontal footprint.
    assert result['dual_quality']['paired_rows'] == 8
    assert result['dual_quality']['embedded_marks'] == 12
    assert not result['dual_quality']['needs_review']
    for part in result.get('parts', [result]):
        assert part['cut_corridor']['pixel_verified']
        with Image.open(tmp_path/'out'/part['filename']) as output:
            for p in part['placements']:
                with Image.open(tmp_path/p['source']) as source:
                    original = np.asarray(source)
                cropped = np.asarray(output.crop((p['x_px'], p['y_px'],
                    p['x_px']+p['width_px'], p['y_px']+p['height_px'])))
                ink = original[:, :, 3] > 0
                assert np.array_equal(original[ink], cropped[ink])
                embedded = int(p['source'].split('-')[0][1:]) < 12
                assert (p['color_block_x_px'] == p['x_px']) == embedded
                assert output.getpixel((p['color_block_x_px'], p['color_block_y_px'])) == (255, 0, 0, 255)
    # An independently altered mark is rejected, not permitted by a blanket image allowance.
    path, p = payloads[0]['planned'][0]
    with pytest.raises(ValueError, match='覆盖原图'):
        validate_embedded_marks([(path, replace(p, color_block_y_px=p.y_px+80))])


def test_added_text_stays_inside_membrane_label_height_and_never_below_it(tmp_path):
    path = make_batch(tmp_path)[0]
    config = LayoutSettings(
        dpi=25.4,
        media_width_mm=580,
        margin_mm=0,
        cutter_mode='dual',
        cutter_auto_knife=True,
        allow_rotation=False,
        cutter_left_marker_external=True,
        preserve_header_gap=True,
        platform_below_marker=True,
        label_text_template='',
        label_source_order_enabled=True,
        label_batch_name='609162025022',
        label_machine_enabled=True,
        label_sequence_enabled=False,
    )
    payloads = []
    generate_layout(
        [path], tmp_path/'preview', config, preview_only=True,
        plan_ready=payloads.append,
    )
    placement = payloads[0]['planned'][0][1]
    label = payloads[0]['labels'][1]
    band = detect_guide_band(path)
    top = placement.y_px+round(band.top*placement.height_px)
    bottom = placement.y_px+round(band.bottom*placement.height_px)

    assert top <= placement.number_y_px
    assert placement.number_y_px+placement.number_height_px <= bottom
    assert placement.x_px <= placement.number_x_px
    assert placement.number_x_px+placement.number_width_px <= (
        placement.color_block_x_px+placement.footprint_width_px
    )
    assert placement.color_block_x_px+placement.color_block_width_px == placement.x_px
    assert '尺码 M' in label
    assert 'M1' in label and '609162025022' in label
    assert placement.number_x_px+placement.number_width_px <= (
        placement.x_px+floor(band.left*placement.width_px)
    )
    with pytest.raises(ValueError, match='图片内部一侧'):
        validate_embedded_marks([
            (path, replace(placement, number_y_px=bottom+1))
        ], config)


@pytest.mark.parametrize('degrees', [0, 90, -90])
def test_narrow_header_uses_verified_gutter_between_mark_and_source(tmp_path, degrees):
    path = make_batch(tmp_path)[-1]
    config = LayoutSettings(
        dpi=25.4, media_width_mm=580, cutter_mode='single',
        allow_rotation=False, cutter_left_marker_external=True,
        preserve_header_gap=True, platform_below_marker=True,
        platform_reuse_qr=True, label_source_order_enabled=True,
        label_batch_name='609162025022', label_machine_enabled=True,
        manual_rotations=((str(path.resolve()), degrees),) if degrees else (),
    )
    result = generate_layout([path], tmp_path/'out', config)
    placement = result['placements'][0]
    assert placement['color_block_x_px']+placement['color_block_width_px'] <= placement['number_x_px']
    from automatic_print.layout_engine.domain.models import Placement
    planned = Placement(**placement)
    if degrees:
        from automatic_print.layout_engine.labeling.markers.marker_stack import in_short_edge_space
        band = detect_guide_band(path).rotated(degrees)
        assert not result['analysis'].get('header_space_recovery')
        assert in_short_edge_space(band, planned.width_px, planned.height_px,
            (planned.number_x_px-planned.x_px, planned.number_y_px-planned.y_px,
             planned.number_width_px, planned.number_height_px))
        assert planned.number_y_px >= planned.y_px
        assert planned.number_y_px+planned.number_height_px <= planned.y_px+planned.height_px
    else:
        band = detect_guide_band(path)
        assert placement['number_x_px'] >= placement['x_px']+ceil(band.right*placement['width_px'])
        with pytest.raises(ValueError, match='图片内部一侧'):
            validate_embedded_marks([(
                path, replace(planned, number_x_px=planned.x_px),
            )], replace(config, preserve_header_gap=False))
    with Image.open(tmp_path/'out'/result['filename']) as output:
        box = (placement['number_x_px'], placement['number_y_px'],
               placement['number_x_px']+placement['number_width_px'],
               placement['number_y_px']+placement['number_height_px'])
        assert output.crop(box).getchannel('A').getbbox()

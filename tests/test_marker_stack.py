import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest
from PIL import Image

from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.models import mm_to_px
from automatic_print.layout_engine.marker_stack import validate_stack
from test_marker_examples import sources


def test_explicit_stack_font_does_not_search_membrane_card(monkeypatch):
    from automatic_print.layout_engine import platform_label
    def unexpected_search(*args):
        raise AssertionError('外置明确字号无需搜索膜标签')
    monkeypatch.setattr(platform_label, 'detect_guide_band', unexpected_search)
    settings = LayoutSettings(dpi=25.4, platform_name='隆丰',
        platform_below_marker=True, platform_font_height_mm=6)
    x, y, width, height = platform_label.platform_geometry(Path('unused.png'), settings, 270, 300, 90)
    assert (x, y, height) == (0, 0, 6)
    assert width > 0


@pytest.mark.parametrize('mode', ['free', 'single', 'dual'])
@pytest.mark.parametrize('side', ['left', 'right'])
@pytest.mark.parametrize('degrees', [0, 90])
def test_platform_and_label_are_one_column_under_marker(tmp_path, mode, side, degrees):
    paths = sources(tmp_path)
    path = paths[0 if side == 'left' else 1]
    settings = LayoutSettings(dpi=25.4, media_width_mm=580, cutter_mode=mode,
        cutter_auto_knife=True, cutter_left_marker_external=True, cutter_left_marker_lift_mm=1.5,
        preserve_header_gap=True, platform_below_marker=True, platform_name='隆丰',
        platform_font_height_mm=6, label_text_template='标签 M1 {编号}', cutter_knife_dots=False,
        manual_rotations=((str(path.resolve()), degrees),), allow_rotation=False)
    payloads = []
    result = generate_layout([path], tmp_path/'out', settings, plan_ready=payloads.append)
    p = payloads[0]['planned'][0][1]
    validate_stack(path, p, payloads[0]['settings'])
    assert p.platform_x_px == p.number_x_px == p.color_block_x_px == 0
    assert p.platform_y_px == p.color_block_y_px+p.color_block_height_px+mm_to_px(settings.number_gap_mm, settings.dpi)
    assert p.number_y_px >= p.platform_y_px+p.platform_height_px
    assert p.x_px > max(p.number_width_px, p.platform_width_px, p.color_block_width_px)
    with Image.open(tmp_path/'out'/result['filename']) as output, Image.open(path) as original:
        with original.rotate(degrees, expand=True) as source:
            pixels = np.asarray(output.crop((p.x_px, p.y_px, p.x_px+source.width, p.y_px+source.height)))
            expected = np.asarray(source)
            mask = expected[:,:,3] > 0
            assert np.array_equal(pixels[mask], expected[mask])
    with pytest.raises(ValueError, match='平台文字未在刀码正下方'):
        validate_stack(path, replace(p, platform_x_px=p.platform_x_px+1), settings)


@pytest.mark.parametrize('engine', ['pillow', 'libvips'])
def test_segmented_double_batch_stack_and_full_saved_corridors(tmp_path, engine):
    sample_paths = sources(tmp_path)
    paths = []
    for order in range(6):
        for face in (1, 2):
            path = tmp_path/f'B{order}-1-T-Black-M-NO1-{face}.png'
            with Image.open(sample_paths[order % 2]) as source:
                source.save(path, dpi=(25.4,25.4))
            paths.append(path)
    settings = LayoutSettings(dpi=25.4, media_width_mm=580, cutter_mode='dual',
        cutter_auto_knife=True, platform_name='隆丰', platform_font_height_mm=6,
        platform_below_marker=True, preserve_header_gap=True, cutter_left_marker_external=True,
        cutter_left_marker_lift_mm=1.5, cutter_knife_dots=False, allow_rotation=False,
        output_parts=3, save_memory_unlimited=True, png_engine=engine)
    result = generate_layout(paths, tmp_path/'out', settings)
    assert result['order_check']['double_pairs'] == 6
    for part in result['parts']:
        with Image.open(tmp_path/'out'/part['filename']) as output:
            for row in part['placements']:
                from automatic_print.layout_engine.models import Placement
                p = Placement(**row)
                validate_stack(Path(p.source), p, settings)
                assert p.platform_x_px+p.platform_width_px <= p.x_px
                with Image.open(tmp_path/p.source) as source:
                    expected = np.asarray(source)
                    pixels = np.asarray(output.crop((p.x_px,p.y_px,p.x_px+source.width,p.y_px+source.height)))
                    mask = expected[:,:,3] > 0
                    assert np.array_equal(pixels[mask], expected[mask])
            for zone in part['cut_corridor'].get('zones', [part['cut_corridor']]):
                assert output.crop((zone['safe_left_px'],zone.get('start_y_px',0),
                    zone['safe_right_px'],zone.get('end_y_px',output.height))).getchannel('A').getextrema()[1] == 0

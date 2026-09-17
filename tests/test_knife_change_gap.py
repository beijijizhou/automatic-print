from pathlib import Path
from PIL import Image

from automatic_print.layout_engine import LayoutSettings, Placement, generate_layout
from automatic_print.layout_engine.cutting.geometry.knife_change_gap import (
    apply_knife_change_gap, inspect_knife_change_gaps,
)
from automatic_print.layout_engine.cutting.validation.cut_validation import validate_cut_corridor
from automatic_print.layout_engine.output.output_sizes import cutting_description


def placement(sequence, row_y, marker_x, knives, zone):
    return Placement(
        source=f'{sequence}.png', sequence_number=sequence,
        x_px=marker_x + 20, y_px=row_y + 10, width_px=80, height_px=80,
        number_x_px=0, number_y_px=row_y + 90,
        number_width_px=0, number_height_px=0,
        row_y_px=row_y, footprint_width_px=100, footprint_height_px=100,
        color_block_x_px=marker_x, color_block_y_px=row_y + 10,
        color_block_width_px=10, color_block_height_px=10,
        cut_zone=zone, cut_knife_x_px=knives[0] if knives else None,
        cut_knife_xs_px=knives, cut_column_count=len(knives) + 1,
    )


def test_knife_change_pushes_next_left_marker_to_570_mm():
    paths = [Path(f'{index}.png') for index in range(1, 5)]
    planned = [
        (paths[0], placement(1, 0, 0, (100,), '并排区')),
        (paths[1], placement(2, 0, 100, (100,), '并排区')),
        (paths[2], placement(3, 100, 0, (), '旋转区')),
        (paths[3], placement(4, 100, 140, (), '旋转区')),
    ]
    settings = LayoutSettings(
        dpi=25.4, cutter_mode='dual', cutter_safety_mm=0,
        cutter_knife_change_gap_mm=570)
    result, changes = apply_knife_change_gap(
        (planned, {}, 580, 200, 200), settings)
    shifted, _labels, _width, height, _baseline = result
    assert changes[0]['added_px'] == 470
    assert height == 670
    second_row = [p for _path, p in shifted if p.row_y_px > 0]
    assert {p.row_y_px for p in second_row} == {570}
    assert {p.color_block_y_px for p in second_row} == {580}
    assert {p.y_px for p in second_row} == {580}
    verified = inspect_knife_change_gaps(shifted, settings)
    assert verified[0]['actual_px'] == verified[0]['required_px'] == 570
    safe_plan = [(path, p) for path, p in shifted if p.sequence_number != 4]
    check = validate_cut_corridor(safe_plan, settings, 580)
    assert check['knife_change_gaps'][0]['actual_px'] == 570
    text = cutting_description({
        'filename': 'test.png', 'size_range': 'S-L', 'placements': [
            {'cut_zone': p.cut_zone} for _path, p in safe_plan],
        'output_dpi': settings.dpi, 'cut_corridor': check,
    })
    assert '刀位切换停止距离' in text
    assert '左侧识别刀码 570.0 毫米' in text


def test_same_knife_does_not_add_stop_distance():
    paths = [Path('1.png'), Path('2.png')]
    planned = [
        (paths[0], placement(1, 0, 0, (100,), '并排区')),
        (paths[1], placement(2, 100, 0, (100,), '并排区')),
    ]
    settings = LayoutSettings(
        dpi=25.4, cutter_mode='dual', cutter_knife_change_gap_mm=570)
    result, changes = apply_knife_change_gap(
        (planned, {}, 580, 200, 200), settings)
    assert result[3] == 200
    assert not changes


def test_real_two_zone_output_keeps_570_mm_left_marker_stop_distance(tmp_path):
    paths = []
    for index, (width, height) in enumerate(
            ((250, 100), (250, 100), (250, 100), (250, 100), (350, 600)), 1):
        path = tmp_path/f'B{index}-1-T-Black-M-NO1-1.png'
        Image.new('RGBA', (width, height), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)
    result = generate_layout(paths, tmp_path/'out', LayoutSettings(
        dpi=25.4, media_width_mm=580, margin_mm=0, spacing_mm=8,
        cutter_mode='dual', cutter_auto_knife=True,
        cutter_rotation_zone=True, cutter_majority_two_zone=True,
        cutter_left_marker_external=True, cutter_safety_mm=0,
        cutter_knife_change_gap_mm=570, number_images=False,
    ))
    change = result['cut_corridor']['knife_change_gaps'][0]
    assert change['actual_px'] == change['required_px'] == 570
    assert [zone['name'] for zone in result['cut_corridor']['zones']] == [
        '并排区', '旋转区']
    assert result['cut_corridor']['pixel_verified']
    assert '刀位切换停止距离' in cutting_description(result)
    with Image.open(tmp_path/'out'/result['filename']) as output:
        assert output.size == (result['width_px'], result['height_px'])

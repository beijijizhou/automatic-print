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


def test_knife_change_pushes_next_left_marker_to_600_mm():
    paths = [Path(f'{index}.png') for index in range(1, 5)]
    planned = [
        (paths[0], placement(1, 0, 0, (100,), '并排区')),
        (paths[1], placement(2, 0, 100, (100,), '并排区')),
        (paths[2], placement(3, 100, 0, (), '旋转区')),
        (paths[3], placement(4, 100, 140, (), '旋转区')),
    ]
    settings = LayoutSettings(
        dpi=25.4, cutter_mode='dual', cutter_safety_mm=0,
        cutter_knife_change_gap_mm=600)
    result, changes = apply_knife_change_gap(
        (planned, {}, 580, 200, 200), settings)
    shifted, _labels, _width, height, _baseline = result
    assert changes[0]['added_px'] == 500
    assert changes[1]['to_zone'] == '批次结束'
    assert changes[1]['added_px'] == 510
    assert changes[1]['distance_reference'] == '上一枚左侧识别刀码起点'
    assert height == 1210
    second_row = [p for _path, p in shifted if p.row_y_px > 0]
    assert {p.row_y_px for p in second_row} == {600}
    assert {p.color_block_y_px for p in second_row} == {610}
    assert {p.y_px for p in second_row} == {610}
    verified = inspect_knife_change_gaps(shifted, settings, height)
    assert verified[0]['actual_px'] == verified[0]['required_px'] == 600
    assert verified[1]['actual_px'] == verified[1]['required_px'] == 600
    safe_plan = [(path, p) for path, p in shifted if p.sequence_number != 4]
    check = validate_cut_corridor(safe_plan, settings, 580, canvas_height=height)
    assert check['knife_change_gaps'][0]['actual_px'] == 600
    text = cutting_description({
        'filename': 'test.png', 'size_range': 'S-L', 'placements': [
            {'cut_zone': p.cut_zone} for _path, p in safe_plan],
        'output_dpi': settings.dpi, 'cut_corridor': check,
    })
    assert '换刀与批次结束停止距离' in text
    assert '从上一枚左侧识别刀码起点计算 600.0 毫米' in text


def test_same_knife_only_adds_batch_end_stop_distance():
    paths = [Path('1.png'), Path('2.png')]
    planned = [
        (paths[0], placement(1, 0, 0, (100,), '并排区')),
        (paths[1], placement(2, 100, 0, (100,), '并排区')),
    ]
    settings = LayoutSettings(
        dpi=25.4, cutter_mode='dual', cutter_knife_change_gap_mm=600)
    result, changes = apply_knife_change_gap(
        (planned, {}, 580, 200, 200), settings)
    assert result[3] == 710
    assert len(changes) == 1
    assert changes[0]['from_zone'] == '并排区'
    assert changes[0]['to_zone'] == '批次结束'
    assert changes[0]['actual_px'] == changes[0]['required_px'] == 600
    last_marker_start = planned[-1][1].color_block_y_px
    last_marker_end = last_marker_start + planned[-1][1].color_block_height_px
    assert result[3] - last_marker_start == 600
    assert result[3] - last_marker_end == 590


def test_single_column_dual_result_reports_batch_end_stop_distance():
    path = Path('1.png')
    planned = [(path, placement(1, 0, 0, (), '单排区'))]
    settings = LayoutSettings(
        dpi=25.4, cutter_mode='dual', cutter_knife_change_gap_mm=600)
    result, _changes = apply_knife_change_gap(
        (planned, {}, 430, 100, 100), settings)

    check = validate_cut_corridor(
        result[0], settings, 430, canvas_height=result[3])

    assert check['column_count'] == 1
    assert check['knife_change_gaps'][-1]['to_zone'] == '批次结束'
    assert check['knife_change_gaps'][-1]['actual_px'] == 600


def test_free_layout_ignores_persisted_cutter_gap_and_markers():
    path = Path('1.png')
    planned = [(path, placement(1, 0, 240, (100,), '旧切膜区'))]
    settings = LayoutSettings(
        dpi=25.4, cutter_mode='free', cutter_knife_change_gap_mm=600,
        cutter_left_marker_external=True,
    )

    assert validate_cut_corridor(
        planned, settings, 580, canvas_height=100,
    ) is None


def test_both_knife_change_directions_and_batch_end_are_protected():
    paths = [Path(f'{index}.png') for index in range(1, 4)]
    planned = [
        (paths[0], placement(1, 0, 0, (100,), '并排区')),
        (paths[1], placement(2, 100, 0, (), '旋转区')),
        (paths[2], placement(3, 200, 0, (100,), '并排区')),
    ]
    settings = LayoutSettings(
        dpi=25.4, cutter_mode='dual', cutter_knife_change_gap_mm=550)

    result, changes = apply_knife_change_gap(
        (planned, {}, 580, 300, 300), settings)

    assert [(row['from_zone'], row['to_zone']) for row in changes] == [
        ('并排区', '旋转区'), ('旋转区', '并排区'), ('并排区', '批次结束'),
    ]
    assert all(row['actual_px'] == row['required_px'] == 550 for row in changes)
    assert all(row['actual_px'] >= row['required_px'] for row in
               inspect_knife_change_gaps(result[0], settings, result[3]))


def test_real_two_zone_output_keeps_600_mm_left_marker_stop_distance(tmp_path):
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
        cutter_knife_change_gap_mm=600, number_images=False,
    ))
    change = result['cut_corridor']['knife_change_gaps'][0]
    assert change['actual_px'] == change['required_px'] == 600
    batch_end = result['cut_corridor']['knife_change_gaps'][-1]
    assert batch_end['to_zone'] == '批次结束'
    assert batch_end['actual_px'] >= batch_end['required_px'] == 600
    assert [zone['name'] for zone in result['cut_corridor']['zones']] == [
        '并排区', '旋转区']
    assert result['cut_corridor']['pixel_verified']
    assert '换刀与批次结束停止距离' in cutting_description(result)
    with Image.open(tmp_path/'out'/result['filename']) as output:
        assert output.size == (result['width_px'], result['height_px'])

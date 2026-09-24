from PIL import Image

from automatic_print.layout_engine import LayoutSettings, generate_layout
from automatic_print.layout_engine.planning.base.planner import plan_layout


def _source(root, index, height):
    path = root / f'B{index}-1-T-Black-M-NO1-1.png'
    Image.new('RGBA', (240, height), 'blue').save(path, dpi=(25.4, 25.4))
    return path


def _settings(**values):
    defaults = dict(
        dpi=25.4,
        media_width_mm=580,
        margin_mm=0,
        spacing_mm=8,
        cutter_mode='dual',
        cutter_auto_knife=True,
        counting_accuracy_layout=True,
        cutter_left_marker_external=True,
        number_images=True,
        label_sequence_enabled=True,
        label_text_template='{编号}/{总数}',
    )
    defaults.update(values)
    return LayoutSettings(**defaults)


def test_counting_layout_numbers_final_canvas_and_keeps_double_rows_exact(tmp_path):
    paths = [
        _source(tmp_path, index, height)
        for index, height in enumerate((100, 420, 180, 340, 260), 1)
    ]
    planned, labels, _width, _height, _baseline = plan_layout(
        paths, _settings(), None,
    )
    spatial = sorted(
        planned,
        key=lambda row: (row[1].row_y_px, row[1].x_px, row[1].y_px),
    )
    assert [placement.sequence_number for _path, placement in spatial] == [1, 2, 3, 4, 5]
    assert [dict(planned)[path].sequence_number for path in paths] != [1, 2, 3, 4, 5]
    assert labels == {index: f'{index}/5' for index in range(1, 6)}

    rows = {}
    for path, placement in planned:
        rows.setdefault((placement.cut_zone, placement.row_y_px), []).append((path, placement))
    regular = [members for (zone, _row), members in rows.items() if zone == '并排区']
    rotated = [members for (zone, _row), members in rows.items() if zone == '旋转区']
    assert regular and all(len(members) == 2 for members in regular)
    assert all(not placement.rotation_degrees for members in regular for _path, placement in members)
    ordered_regular = sorted(
        regular,
        key=lambda members: members[0][1].row_y_px,
    )
    for row_index, members in enumerate(ordered_regular):
        left, right = sorted(members, key=lambda member: member[1].x_px)
        assert [left[1].sequence_number, right[1].sequence_number] == [
            row_index * 2 + 1,
            row_index * 2 + 2,
        ]
    assert rotated and all(len(members) == 1 for members in rotated)


def test_existing_layout_keeps_legacy_single_row_when_trial_is_off(tmp_path):
    paths = [_source(tmp_path, index, 100 + index * 20) for index in range(1, 4)]
    planned = plan_layout(paths, _settings(
        counting_accuracy_layout=False,
        cutter_majority_two_zone=False,
        cutter_rotation_zone=False,
        number_images=False,
        label_sequence_enabled=False,
    ), None)[0]
    rows = {}
    for path, placement in planned:
        rows.setdefault(placement.row_y_px, []).append((path, placement))
    assert any(len(members) == 1 for members in rows.values())


def test_counting_layout_generates_validated_png_without_mixed_double_rows(tmp_path):
    paths = [_source(tmp_path, index, height)
             for index, height in enumerate((120, 360, 180, 300, 240), 1)]
    result = generate_layout(paths, tmp_path / 'output', _settings())
    rows = {}
    for placement in result['placements']:
        rows.setdefault((placement['cut_zone'], placement['row_y_px']), []).append(placement)
    assert all(len(members) == 2 for (zone, _row), members in rows.items()
               if zone == '并排区')
    assert all(len(members) == 1 for (zone, _row), members in rows.items()
               if zone == '旋转区')
    assert result['cut_corridor']['pixel_verified']
    assert (tmp_path / 'output' / result['filename']).is_file()

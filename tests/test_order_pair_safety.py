from dataclasses import replace
from itertools import product

from PIL import Image
import pytest

from automatic_print.layout import LayoutSettings, generate_layout
from automatic_print.layout_engine.order_groups import ordered_paths, pair_identity
from automatic_print.layout_engine.order_validation import validate_order_placements
from automatic_print.layout_engine.planner import plan_layout
from automatic_print.layout_engine.rotation_zones import _normal, _rotated, complete_orders


def source(tmp_path, name, width=100, height=220):
    path = tmp_path / f'{name}.png'
    Image.new('RGBA', (width, height), 'blue').save(path, dpi=(25.4,25.4))
    return path


def settings(**kwargs):
    return replace(LayoutSettings(dpi=25.4, number_images=False, margin_mm=0,
        cutter_mode='dual', cutter_auto_knife=True, cutter_rotation_zone=True), **kwargs)


def test_export_prefix_and_interleaving_cannot_separate_sides_or_orders(tmp_path):
    a = source(tmp_path, 'CVC面料00001-BORDER-1-T-White-XXL-NO1-1', 100, 167)
    other = source(tmp_path, 'CVC面料00002-BOTHER-1-T-White-M-NO1-1')
    b = source(tmp_path, 'CVC面料00003-BORDER-1-T-White-XXL-NO1-2', 243, 372)
    small = source(tmp_path, 'A0000004-BORDER-2-T-White-S-NO1-1')
    paths = [a, other, b, small]
    planned = plan_layout(paths, settings(cutter_rotation_zone=False), None)[0]
    assert [p for p, _ in planned] == [small, a, b, other]
    by_path = dict(planned)
    assert by_path[a].y_px == by_path[b].y_px
    assert by_path[a].x_px != by_path[b].x_px
    assert {by_path[a].sequence_number, by_path[b].sequence_number} == {1, 3}
    assert validate_order_placements(paths, planned)['double_pairs'] == 1
    broken = [planned[0], planned[1], planned[-1], planned[2]]
    with pytest.raises(ValueError, match='插入'):
        validate_order_placements(paths, broken)


def test_two_orders_can_rotate_together_when_neither_single_move_saves(tmp_path):
    paths = [source(tmp_path, f'B{order}-1-NO1-1') for order in ('ONE', 'TWO')]
    normal_settings = settings(cutter_rotation_zone=False)
    baseline = plan_layout(paths, normal_settings, None)
    for path in paths:
        remaining = [p for p in paths if p != path]
        assert _normal(remaining, normal_settings)[0][3] + normal_settings.spacing_mm + _rotated([path], normal_settings)[2] > baseline[3]
    planned, _, _, height, _ = plan_layout(paths, settings(), None)
    assert height == 200 + normal_settings.spacing_mm
    assert height < baseline[3]
    assert all(p.cut_zone == '旋转区' for _, p in planned)


def test_assignment_matches_exhaustive_whole_order_comparison(tmp_path):
    paths = [source(tmp_path, f'B{i}-1-NO1-{side}', w, h)
             for i, (w, h, sides) in enumerate(((100, 250, 2), (200, 150, 1), (80, 240, 1), (90, 200, 2)))
             for side in range(1, sides+1)]
    base = settings(cutter_rotation_zone=False, margin_mm=3)
    orders = complete_orders(paths)
    heights = []
    for mask in product((False, True), repeat=len(orders)):
        normal = [p for use, order in zip(mask, orders) if not use for p in order]
        rotated = [p for use, order in zip(mask, orders) if use for p in order]
        n = _normal(normal, base)[0][3] if normal else 0
        r = _rotated(rotated, base)[2] if rotated else 0
        heights.append(n+r+(base.spacing_mm if normal and rotated else 0))
    assert plan_layout(paths, settings(margin_mm=3), None)[3] == min(heights)


def test_all_batch_pairs_and_pixel_corridors_are_checked(tmp_path):
    paths = []
    for i in range(6):
        w, h = (100, 300) if i < 3 else (200, 150)
        for side in (1, 2):
            paths.append(source(tmp_path, f'CVC面料{i*2+side:05}-B{i}-1-T-White-L-NO1-{side}', w, h))
    result = generate_layout(paths, tmp_path/'out', settings())
    assert result['order_check']['double_pairs'] == 6
    assert result['cut_corridor']['checked_images'] == 12
    assert result['cut_corridor']['pixel_verified']
    assert all(z['pixel_verified'] for z in result['cut_corridor'].get('zones', [result['cut_corridor']]))
    for group in complete_orders(paths):
        members = [p for p in result['placements'] if p['source'] in {s.name for s in group}]
        assert len({p['cut_zone'] for p in members}) == 1


def test_unknown_identity_is_kept_as_a_conservative_group(tmp_path):
    a = tmp_path/'a.png'; b = tmp_path/'b.png'; c = tmp_path/'BORDER-1-NO1-1.png'
    assert ordered_paths([a,c,b]) == [a,b,c]


def test_already_normalized_order_code_is_not_stripped_again(tmp_path):
    from automatic_print.layout_engine.order_groups import order_key
    assert order_key(tmp_path/'A0000007-1-T-White-L-NO1-1.png') == 'a0000007'
    assert order_key(tmp_path/'A0000001-BORDER-1-T-White-L-NO1-1.png') == 'border'


def test_rotation_can_fit_batch_without_a_feasible_normal_baseline(tmp_path):
    paths = [source(tmp_path, 'BORDER-1-NO1-1', 700, 100)]
    with pytest.raises(ValueError):
        plan_layout(paths, settings(cutter_rotation_zone=False), None)
    planned, _, _, _, _ = plan_layout(paths, settings(), None)
    assert planned[0][1].cut_zone == '旋转区'

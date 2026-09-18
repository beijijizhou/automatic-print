from dataclasses import replace
from itertools import permutations
from pathlib import Path
from random import Random

from automatic_print.layout_engine import LayoutSettings
from automatic_print.layout_engine.intake.preparation.item_factory import LayoutItem
from automatic_print.layout_engine.planning.columns.cutter_planner import _horizontal, _lanes, solve_groups
from automatic_print.layout_engine.planning.columns.column_solver import solve_group_choices
from automatic_print.layout_engine.orders.single_order_sequence import (
    arrange_groups, arrange_groups_within_orders, arrange_order_groups,
    horizontal_savings,
)
from automatic_print.layout_engine.planning.columns.dynamic_columns import select_columns
from automatic_print.layout_engine.planning.columns.choice.planner import riin_sequence_height

def item(i, width, height, offset=0):
    return LayoutItem(Path(f'B{i}-1-T-Black-M-NO1-1.png'), i, width-15, height,
        15, offset, 0, 15, 0, 0, width, height+offset, 0, 0, 0, 10, 10)


def test_numeric_pair_cost_matches_real_placement_geometry():
    rng = Random(7)
    for i in range(200):
        a, b = [item(j, rng.randrange(50, 400), rng.randrange(50, 400), rng.randrange(5)) for j in (1, 2)]
        lanes = _lanes(LayoutSettings(dpi=25.4, cutter_knife_mm=rng.randrange(100, 480)), 600)
        row = _horizontal([a, b], lanes)
        expected = a.footprint_height+b.footprint_height-row.height if row else None
        assert horizontal_savings(a, b, lanes) == expected


def test_riin_baseline_is_untouched_next_fit_sequence():
    items = [item(1, 200, 100), item(2, 250, 120), item(3, 180, 80)]
    assert riin_sequence_height(items, 500, 5) == 120 + 5 + 80


def test_riin_choice_can_pair_adjacent_colours_but_optimized_choice_cannot():
    black = replace(item(1, 200, 100),
                    path=Path('BLACK-1-T-Black-M-NO1-1.png'))
    white = replace(item(2, 200, 100),
                    path=Path('WHITE-1-T-White-M-NO1-1.png'))
    choices = [[[black]], [[white]]]
    lanes = [(0, 300, None), (300, 600, 300)]
    optimized = solve_group_choices(
        choices, lanes, 5, pair_adjacent=True,
        allow_order_boundary=True, allow_any_adjacent=False,
    )
    riin = solve_group_choices(
        choices, lanes, 5, pair_adjacent=True,
        allow_order_boundary=True, allow_any_adjacent=True,
    )
    assert optimized[0] == 210
    assert riin[0] == 105


def test_multi_piece_order_reorders_local_pieces_to_fill_both_lanes():
    lanes = [(0, 400, None), (400, 600, 400)]
    groups = [[replace(item(index, width, height),
                       path=Path(f'BORDER-{index}-T-Black-M-NO1-1.png'))]
              for index, (width, height) in enumerate(
                  ((350, 300), (350, 280), (180, 250), (180, 230)), 1)]
    before = solve_groups(groups, lanes, 5)
    arranged = arrange_order_groups(groups, lanes)
    after = solve_groups(arranged, lanes, 5)
    assert [group[0].footprint_width for group in arranged] == [350, 180, 350, 180]
    assert after[0] < before[0]
    assert all(
        group[0].path.name.startswith('BORDER-') for group in arranged
    )


def test_order_local_matching_uses_best_combination_not_first_greedy_pair(monkeypatch):
    from automatic_print.layout_engine.orders import single_order_sequence

    groups = [[replace(item(index, 200, 100),
                       path=Path(f'BORDER-{index}-T-Black-M-NO1-1.png'))]
              for index in range(4)]
    values = {(0, 1): 10, (0, 2): 6, (1, 3): 6, (2, 3): 1}
    monkeypatch.setattr(
        single_order_sequence, 'horizontal_savings',
        lambda first, second, _lanes: values.get(
            tuple(sorted((first.index, second.index)))
        ),
    )
    arranged = single_order_sequence.arrange_order_groups(groups, [(0, 300), (300, 600)])
    assert [group[0].index for group in arranged] == [0, 2, 1, 3]


def test_preserved_order_sequence_still_pairs_pieces_inside_each_order():
    lanes = [(0, 400, None), (400, 600, 400)]
    groups = []
    for order in ('AORDER', 'BORDER'):
        groups.extend([[replace(item(index, width, height),
                                path=Path(f'{order}-{index}-T-Black-M-NO1-1.png'))]
                       for index, (width, height) in enumerate(
                           ((350, 300), (350, 280), (180, 250), (180, 230)), 1)])
    arranged = arrange_groups_within_orders(groups, lanes)
    names = [group[0].path.name for group in arranged]
    assert all(name.startswith('AORDER-') for name in names[:4])
    assert all(name.startswith('BORDER-') for name in names[4:])
    assert [group[0].footprint_width for group in arranged[:4]] in (
        [350, 180, 350, 180], [350, 180, 180, 350],
    )


def test_adjacent_order_boundaries_can_share_one_row_without_splitting_orders():
    lanes = [(0, 300, None), (300, 600, 300)]
    groups = [[replace(item(index, 200, 100),
                       path=Path(f'{order}-{piece}-T-Black-M-NO1-1.png'))]
              for index, (order, piece) in enumerate((
                  ('AORDER', 1), ('AORDER', 2), ('AORDER', 3),
                  ('BORDER', 1), ('BORDER', 2), ('BORDER', 3),
              ), 1)]
    solution = solve_groups(
        groups, lanes, 5, pair_adjacent=True, allow_order_boundary=True,
    )
    assert solution is not None
    assert solution[0] == 3 * (100 + 5)


def test_multi_column_matching_preserves_permutation_first_result():
    rng = Random(23)
    for count in range(2, 9):
        lanes = [(index * 100, (index + 1) * 100, None if index == 0 else index * 100)
                 for index in range(count)]
        for _ in range(30):
            group = [replace(item(index, rng.randrange(45, 115), 100),
                             block_rx=rng.randrange(0, 25))
                     for index in range(count)]
            expected = None
            from automatic_print.layout_engine.planning.columns.column_solver import member
            for assigned in permutations(lanes):
                candidate = [member(value, lane) for value, lane in zip(group, assigned)]
                if not any(value is None for value in candidate):
                    expected = candidate
                    break
            actual = _horizontal(group, lanes)
            if expected is None:
                assert actual is None
            else:
                assert [value.x for value in actual.members] == [value.x for value in expected]


def test_eight_column_no_match_uses_bounded_state_search(monkeypatch):
    from automatic_print.layout_engine.planning.columns import column_solver
    lanes = [(index * 100, (index + 1) * 100, None if index == 0 else index * 100)
             for index in range(8)]
    group = [item(index, 101, 100) for index in range(8)]
    original, calls = column_solver.member, []

    def counted(*args):
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(column_solver, 'member', counted)
    assert column_solver.horizontal(group, lanes) is None
    assert len(calls) <= 8 * (2 ** 8)


def test_auto_columns_skip_physically_impossible_three_to_eight(monkeypatch):
    from automatic_print.layout_engine.planning.columns import cutter_planner
    groups = [[item(index, 220, 100)] for index in range(16)]
    original, attempted = cutter_planner.solve_groups, []

    def counted(groups, lanes, spacing, pair_adjacent=False):
        attempted.append(len(lanes))
        return original(groups, lanes, spacing, pair_adjacent)

    monkeypatch.setattr(cutter_planner, 'solve_groups', counted)
    settings = LayoutSettings(
        dpi=25.4, media_width_mm=580, cutter_mode='dual',
        cutter_auto_knife=True, cutter_safety_mm=0,
    )
    select_columns(groups, settings, 5)
    assert attempted
    assert max(attempted) <= 2


def test_auto_columns_keep_physically_possible_three_columns(monkeypatch):
    from automatic_print.layout_engine.planning.columns import cutter_planner
    groups = [[item(index, 150, 100)] for index in range(6)]
    original, attempted = cutter_planner.solve_groups, []

    def counted(groups, lanes, spacing, pair_adjacent=False):
        attempted.append(len(lanes))
        return original(groups, lanes, spacing, pair_adjacent)

    monkeypatch.setattr(cutter_planner, 'solve_groups', counted)
    settings = LayoutSettings(
        dpi=25.4, media_width_mm=600, cutter_mode='dual',
        cutter_auto_knife=True, cutter_safety_mm=0,
    )
    select_columns(groups, settings, 5)
    assert 3 in attempted


def test_auto_columns_compare_lanes_after_multi_piece_local_pairing():
    groups = [[replace(item(index, width, height),
                       path=Path(f'BORDER-{index}-T-Black-M-NO1-1.png'))]
              for index, (width, height) in enumerate(
                  ((350, 300), (350, 280), (180, 250), (180, 230)), 1)]
    settings = LayoutSettings(
        dpi=25.4, media_width_mm=600, cutter_mode='dual',
        cutter_auto_knife=True, cutter_safety_mm=0,
        cutter_majority_two_zone=False,
    )
    _selected, lanes, knives = select_columns(groups, settings, 5)
    assert len(lanes) == 2
    assert len(knives) == 1


def test_auto_columns_do_not_try_four_when_only_two_items_fit_narrow_lanes(monkeypatch):
    from automatic_print.layout_engine.planning.columns import cutter_planner
    groups = [[item(index, width, 100)]
              for index, width in enumerate((120, 130, 220, 220, 220, 220))]
    original, attempted = cutter_planner.solve_groups, []

    def counted(groups, lanes, spacing, pair_adjacent=False):
        attempted.append(len(lanes))
        return original(groups, lanes, spacing, pair_adjacent)

    monkeypatch.setattr(cutter_planner, 'solve_groups', counted)
    settings = LayoutSettings(
        dpi=25.4, media_width_mm=600, cutter_mode='dual',
        cutter_auto_knife=True, cutter_safety_mm=0,
    )
    select_columns(groups, settings, 5)
    assert 4 not in attempted


def test_auto_columns_reject_narrow_lanes_when_any_item_cannot_fit(monkeypatch):
    from automatic_print.layout_engine.planning.columns import cutter_planner
    groups = [[item(index, width, 100)]
              for index, width in enumerate((120, 130, 140, 250))]
    original, attempted = cutter_planner.solve_groups, []

    def counted(groups, lanes, spacing, pair_adjacent=False):
        attempted.append(len(lanes))
        return original(groups, lanes, spacing, pair_adjacent)

    monkeypatch.setattr(cutter_planner, 'solve_groups', counted)
    settings = LayoutSettings(
        dpi=25.4, media_width_mm=600, cutter_mode='dual',
        cutter_auto_knife=True, cutter_safety_mm=0,
    )
    select_columns(groups, settings, 5)
    assert 3 not in attempted
# Event-order regressions continue in test_fast_knife_events.py.

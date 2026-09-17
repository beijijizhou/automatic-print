from dataclasses import replace
from itertools import permutations
from pathlib import Path
from random import Random

from automatic_print.layout_engine import LayoutSettings
from automatic_print.layout_engine.intake.preparation.item_factory import LayoutItem
from automatic_print.layout_engine.planning.columns.cutter_planner import _horizontal, _lanes, solve_groups
from automatic_print.layout_engine.orders.single_order_sequence import arrange_groups, horizontal_savings
from automatic_print.layout_engine.planning.columns.knife_optimizer import select_batch_knife, knife_candidates, distinct_knife_candidates
from automatic_print.layout_engine.planning.columns.dynamic_columns import select_columns


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


def test_deduplicated_search_preserves_exhaustive_best_height_and_knife():
    rng = Random(11)
    for trial in range(12):
        groups = [[item(i, rng.randrange(70, 360), rng.randrange(90, 300))] for i in range(12)]
        settings = LayoutSettings(dpi=25.4, media_width_mm=580, cutter_mode='dual')
        scores = []
        for knife in knife_candidates(groups, settings):
            candidate = replace(settings, cutter_knife_mm=knife)
            lanes = _lanes(candidate, 580)
            result = solve_groups(arrange_groups(groups, lanes, candidate), lanes, 5)
            if result:
                scores.append((result[0], abs(knife-290), knife))
        actual = select_batch_knife(groups, settings, 5)
        assert round(actual.cutter_knife_mm) == min(scores)[2]


def test_range_event_states_match_full_lane_checks_with_marker_offsets():
    from automatic_print.layout_engine.orders.single_order_sequence import lane_fits
    rng = Random(17)
    for _ in range(20):
        groups = [[replace(item(i, rng.randrange(50, 500), 200),
                           block_rx=rng.randrange(-5, 30))] for i in range(20)]
        config = LayoutSettings(dpi=25.4, media_width_mm=580, cutter_mode='dual',
                                cutter_marker_offset_mm=rng.randrange(0, 25))
        states = {}
        for knife in knife_candidates(groups, config):
            lanes = _lanes(replace(config, cutter_knife_mm=knife), 580)
            signature = tuple(lane_fits(g[0], lane) for g in groups for lane in lanes)
            old = states.get(signature)
            if old is None or (abs(knife-290), knife) < (abs(old-290), old):
                states[signature] = knife
        assert distinct_knife_candidates(groups, config) == sorted(states.values())

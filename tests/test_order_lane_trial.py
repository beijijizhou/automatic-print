"""The opt-in two-lane trial keeps every complete order on one side."""
from collections import Counter
from pathlib import Path

import pytest

from automatic_print.layout_engine.domain.models import LayoutItem
from automatic_print.layout_engine.orders.order_groups import order_key
from automatic_print.layout_engine.planning.columns.order_lane_trial import (
    plan_order_sides_rows, trial_order_sides,
)


def item(order, number, height, side=1, width=80, color='Black', size='S'):
    path = Path(f'{order}-{number}-T-{color}-{size}-NO1-{side}.png')
    return LayoutItem(path, number, width, height, 0, 0, 0, 0, 0, 0,
                      width, height, 0, 0, 0, 0, 0)


def test_complete_orders_and_double_faces_stay_in_separate_lanes():
    groups = [
        [item('A', 1, 60, 1), item('A', 1, 60, 2)],
        [item('A', 2, 70, 1), item('A', 2, 70, 2)],
        [item('B', 1, 100)], [item('B', 2, 100)],
    ]
    result = trial_order_sides(groups, [(0, 100, None), (100, 200, 100)], 5, 100)
    assert result['unplaceable_orders'] == []
    assert result['lane_heights_px'] == [275, 205]
    assert result['height_px'] == 275
    assert result['height_gap_px'] == 70
    assert [entry['lane'] for entry in result['assignments']] == [0, 1]
    assert [entry['pieces'] for entry in result['assignments']] == [2, 2]
    assert [entry['images'] for entry in result['assignments']] == [4, 2]
    planned = result['planned']
    assert Counter(path for path, _ in planned) == Counter(
        source.path for group in groups for source in group)
    assert all(placement.cut_knife_x_px == 100 and
               placement.cut_knife_xs_px == (100,) and
               placement.cut_column_count == 2 for _, placement in planned)
    for key, lane in [('a', 0), ('b', 1)]:
        placed = [placement for path, placement in planned if order_key(path) == key]
        assert len(placed) == (4 if key == 'a' else 2)
        assert all((placement.x_px < 100) == (lane == 0) for placement in placed)


def test_width_constrained_order_is_forced_left_as_a_whole():
    groups = [[item('A', 1, 40, width=110)], [item('A', 2, 40, width=110)],
              [item('B', 1, 40, width=60)], [item('B', 2, 40, width=60)]]
    result = trial_order_sides(groups, [(0, 120, None), (120, 200, 120)], 5, 120)
    assert result['unplaceable_orders'] == []
    assert {entry['order']: entry['lane'] for entry in result['assignments']} == {
        'a': 0, 'b': 1}


def test_interleaved_mixed_color_and_size_units_rejoin_their_complete_order():
    groups = [[item('A', 1, 40, color='Black', size='S')],
              [item('B', 1, 45)],
              [item('A', 2, 50, color='White', size='XL')],
              [item('B', 2, 55)]]
    result = trial_order_sides(groups, [(0, 100, None), (100, 200, 100)], 5, 100)
    assert result['unplaceable_orders'] == []
    for key in ('a', 'b'):
        placed = [placement for path, placement in result['planned']
                  if order_key(path) == key]
        assert len(placed) == 2
        assert placed[0].y_px < placed[1].y_px
        assert (placed[0].x_px < 100) == (placed[1].x_px < 100)


def test_unplaceable_order_invalidates_complete_trial_coordinates():
    groups = [[item('A', 1, 40)], [item('B', 1, 40, width=220)]]
    result = trial_order_sides(groups, [(0, 100, None), (100, 200, 100)], 5, 100)
    assert result['unplaceable_orders'] == ['b']
    assert result['height_px'] is None
    assert result['planned'] == []


def test_trial_rejects_single_lane_without_middle_knife():
    with pytest.raises(ValueError, match='两列'):
        trial_order_sides([[item('A', 1, 40)]], [(0, 200, None)], 5, 100)


def test_printable_rows_align_both_lanes_without_splitting_orders():
    groups = [[item('A', 1, 60)], [item('B', 1, 40)],
              [item('A', 2, 70)], [item('B', 2, 50)]]
    planned, height, trial = plan_order_sides_rows(
        groups, [(0, 100, None), (100, 200, 100)], 5, 100, 10)
    assert trial['unplaceable_orders'] == []
    assert len(planned) == 4
    assert [placement.row_y_px for _path, placement in planned] == [10, 10, 75, 75]
    assert height == 155
    assert Counter(path for path, _placement in planned) == Counter(
        source.path for group in groups for source in group)

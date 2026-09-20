"""The isolated two-lane trial never modifies production placements."""
from pathlib import Path

from automatic_print.layout_engine.domain.models import LayoutItem
from automatic_print.layout_engine.planning.columns.order_lane_trial import compare_multi_order_lanes


def item(order, number, height, side=1, width=80):
    path = Path(f'{order}-{number}-T-Black-S-NO1-{side}.png')
    return LayoutItem(path, number, width, height, 0, 0, 0, 0, 0, 0,
                      width, height, 0, 0, 0, 0, 0)


def test_balances_measured_height_not_equal_piece_counts():
    groups = [[item(order, number, height)] for order, height in (
        ('A', 250), ('B', 150), ('C', 100)) for number in (1, 2)]
    result = compare_multi_order_lanes(groups, [(0, 100, None), (100, 200, 100)], 5)
    assert result['lane_pieces'] == [2, 4]
    assert result['lane_heights_px'] == [505, 515]
    assert result['height_gap_px'] == 10
    assert len({entry['order'] for entry in result['assignments']}) == 3


def test_double_faces_and_entire_order_stay_in_one_lane():
    groups = [
        [item('A', 1, 60, 1), item('A', 1, 60, 2)],
        [item('A', 2, 70, 1), item('A', 2, 70, 2)],
        [item('B', 1, 40)],
    ]
    result = compare_multi_order_lanes(groups, [(0, 100, None), (100, 200, 100)], 5)
    assert result['assignments'][0]['order'] == 'a'
    assert result['assignments'][0]['pieces'] == 2
    assert result['assignments'][0]['images'] == 4
    assert result['assignments'][0]['height_px'] == 275
    assert result['excluded_single_orders'] == 1
    assert result['unplaceable_orders'] == []


def test_reports_order_that_fits_neither_lane_without_output():
    groups = [[item('A', 1, 40, width=120)], [item('A', 2, 40, width=120)]]
    result = compare_multi_order_lanes(groups, [(0, 100, None), (100, 200, 100)], 5)
    assert result['assignments'] == []
    assert result['unplaceable_orders'] == ['a']


def test_lane_constrained_order_is_placed_before_flexible_order():
    groups = [[item(order, number, height, width=width)]
              for order, height, width in (('A', 150, 80), ('B', 100, 110))
              for number in (1, 2)]
    result = compare_multi_order_lanes(groups, [(0, 120, None), (120, 200, 120)], 5)
    assert [(entry['order'], entry['lane']) for entry in result['assignments']] == [
        ('b', 0), ('a', 1)]

"""A single-column batch trial stays isolated from production placements."""
from pathlib import Path

import pytest

from automatic_print.layout_engine.domain.models import LayoutItem
from automatic_print.layout_engine.planning.columns.order_lane_trial import trial_single_column_multi_batch


def item(order, number, height, side=1, width=80):
    path = Path(f'{order}-{number}-T-Black-S-NO1-{side}.png')
    return LayoutItem(path, number, width, height, 0, 0, 0, 0, 0, 0,
                      width, height, 0, 0, 0, 0, 0)


def test_every_complete_order_and_double_pair_uses_one_uncut_column():
    groups = [
        [item('A', 1, 60, 1), item('A', 1, 60, 2)],
        [item('A', 2, 70, 1), item('A', 2, 70, 2)],
        [item('B', 1, 100)], [item('B', 2, 100)],
    ]
    result = trial_single_column_multi_batch(groups, (0, 200, None), 5)
    assert [row['order'] for row in result['orders']] == ['a', 'b']
    assert [row['pieces'] for row in result['orders']] == [2, 2]
    assert [row['images'] for row in result['orders']] == [4, 2]
    assert result['piece_count'] == 4 and result['image_count'] == 6
    assert result['height_px'] == 275 + 205 + 5
    assert result['unplaceable_orders'] == []
    assert 'placements' not in result


def test_one_unplaceable_order_invalidates_whole_trial():
    groups = [[item('A', 1, 40)], [item('A', 2, 40)],
              [item('B', 1, 40, width=220)], [item('B', 2, 40)]]
    result = trial_single_column_multi_batch(groups, (0, 200, None), 5)
    assert result['unplaceable_orders'] == ['b']
    assert result['height_px'] is None
    assert result['order_count'] == 2


def test_trial_rejects_a_split_lane_with_a_middle_knife():
    with pytest.raises(ValueError, match='没有中间纵刀'):
        trial_single_column_multi_batch([[item('A', 1, 40)]], (100, 200, 100), 5)

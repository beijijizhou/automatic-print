"""A00 multi-piece batch planning preserves orders and composition boundaries."""

from unittest.mock import patch

import pytest

from automatic_print.automation.batches.received.received_sizes import (
    _chunks,
    _verify_orders,
    plan_received_multi,
)


def _row(item_id, order_id, composition, size, qty=1):
    return {
        "id": item_id,
        "order_id": order_id,
        "order_composition": composition,
        "size": size,
        "qty": qty,
        "status": 1,
        "process_route_code": "A00",
    }


def test_cross_size_first_and_single_item_multi_excluded():
    rows = [
        _row("1", "mixed", 3, "M"),
        _row("2", "mixed", 3, "L"),
        _row("3", "single", 2, "S", 3),
        _row("4", "same", 3, "S"),
        _row("5", "same", 3, "S"),
        _row("6", "ordinary", 1, "XL"),
    ]

    plan = plan_received_multi(rows)

    assert [group.label for group in plan.groups] == [
        "跨尺码·多项多件", "S·多项多件",
    ]
    assert [[item.item_id for item in group.items] for group in plan.groups] == [
        ["1", "2"], ["4", "5"],
    ]
    assert plan.groups[1].piece_count == 2


def test_large_cross_size_group_chunks_only_between_orders():
    rows = []
    for number in range(101):
        order_id = str(number)
        rows.extend((
            _row(f"{number}-a", order_id, 3, "S"),
            _row(f"{number}-b", order_id, 3, "M"),
        ))

    group = plan_received_multi(rows).groups[0]
    chunks = tuple(_chunks(group))

    assert [sum(len(order) for order in chunk) for chunk in chunks] == [200, 2]
    assert [sum(len(chunk) for chunk in chunks)] == [101]


def test_confirmed_batch_must_not_split_one_order():
    order = plan_received_multi([
        _row("1", "mixed", 3, "S"),
        _row("2", "mixed", 3, "M"),
    ]).groups[0].orders[0]
    actual = [
        {**_row("1", "mixed", 3, "S"), "status": 5,
         "production_batch_code": "batch-a"},
        {**_row("2", "mixed", 3, "M"), "status": 5,
         "production_batch_code": "batch-b"},
    ]
    with patch(
        "automatic_print.automation.batches.received.received_sizes.list_order_items",
        return_value=actual,
    ):
        with pytest.raises(RuntimeError, match="拆散"):
            _verify_orders(None, (order,), submitted=True)

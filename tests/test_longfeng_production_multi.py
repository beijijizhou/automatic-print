"""Printed A00 multi-item supplements keep orders whole and ignore color."""

from unittest.mock import patch

from automatic_print.automation.batches.supplements.production_multi import preview_production_multi


SOURCE = ("first", "second")


def _row(item_id, order_id, size, color, source):
    return {
        "id": item_id,
        "order_id": order_id,
        "status": 5,
        "process_route_code": "A00",
        "order_composition": 3,
        "view_count": 1,
        "production_batch_code": source,
        "size": size,
        "color": color,
        "qty": 1,
    }


def test_cross_size_first_and_same_size_colors_together():
    rows = [
        _row("1", "mixed", "S", "黑色", SOURCE[0]),
        _row("2", "mixed", "M", "白色", SOURCE[1]),
        _row("3", "same-a", "S", "黑色", SOURCE[0]),
        _row("4", "same-b", "S", "白色", SOURCE[1]),
    ]
    with patch(
        "automatic_print.automation.batches.supplements.production_multi._all_rows",
        return_value=rows,
    ):
        plan = preview_production_multi(None, SOURCE)

    assert [(group.label, len(group.orders), len(group.items))
            for group in plan.groups] == [
        ("跨尺码", 1, 2),
        ("S", 2, 2),
    ]

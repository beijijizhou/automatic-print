"""A05 no-print supplement grouping keeps colors together and orders intact."""

from unittest.mock import patch

from automatic_print.automation.batches.supplements.supplement_sizes import (
    preview_size_supplements,
)


SOURCE = ("609211939001",)


def _row(item_id, order_id, size, color, *, old_code=""):
    return {
        "id": item_id,
        "order_id": order_id,
        "size": size,
        "color": color,
        "qty": 2,
        "status": 5,
        "process_route_code": "A05",
        "style_code": "T-LSJ-0",
        "production_batch_code": SOURCE[0],
        "supplement_detail_list": (
            [{"production_batch_code": old_code}] if old_code else []
        ),
    }


def test_colors_share_size_group_and_mixed_order_stays_whole():
    rows = [
        _row("1", "a", "S", "黑色"),
        _row("2", "b", "S", "白色"),
        _row("3", "c", "XL", "黑色"),
        _row("4", "d", "XL", "黑色"),
        _row("5", "d", "XXL", "白色", old_code="prior"),
    ]
    with patch(
        "automatic_print.automation.batches.supplements.supplement_sizes._selected_rows",
        return_value=rows,
    ):
        safe_plan = preview_size_supplements(None, SOURCE)
        plan = preview_size_supplements(None, SOURCE, allow_existing_mixed=True)

    assert [group.label for group in safe_plan.groups] == ["S", "XL"]
    assert safe_plan.partial_mixed_order_ids == ("d",)

    assert [(group.label, [item.item_id for item in group.items])
            for group in plan.groups] == [
        ("S", ["1", "2"]),
        ("XL", ["3"]),
        ("跨尺码整单", ["4", "5"]),
    ]
    assert plan.existing_item_count == 1
    assert plan.partial_mixed_order_ids == ("d",)
    assert plan.groups[-1].items[-1].existing_codes == ("prior",)

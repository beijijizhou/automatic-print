import pytest

from automatic_print.automation.batches.classification import (
    BACK_FACE,
    DOUBLE_FACE_DETAIL,
    FRONT_FACE,
    UNKNOWN_FACE_DETAIL,
    classify_production_face,
    size_band,
)
from automatic_print.automation.batches.completed import (
    completed_batch_request,
    plan_completed_haloo_batches,
)


def _row(item, order, *, composition=1, style="base-a", color="黑色", size="M"):
    return {
        "id": item,
        "order_id": order,
        "status": 9,
        "order_composition": composition,
        "logistics_sorting_code": "USPS",
        "style_id": style,
        "style_name": "棉T恤",
        "color": color,
        "size": size,
    }


def _detail(*names):
    return {"production_images": [{"name": name} for name in names]}


def test_face_uses_production_image_names_not_view_count() -> None:
    assert classify_production_face(_detail("A面")) == FRONT_FACE
    assert classify_production_face(_detail("B面")) == BACK_FACE
    assert classify_production_face(_detail("A面", "B面")) == DOUBLE_FACE_DETAIL
    assert classify_production_face(_detail("袖口")) == UNKNOWN_FACE_DETAIL


def test_size_bands_accept_haloo_xxl_alias() -> None:
    assert size_band("S") == "S-XL"
    assert size_band("XL") == "S-XL"
    assert size_band("XXL") == "2XL-5XL"
    assert size_band("5xl") == "2XL-5XL"


def test_completed_plan_keeps_multi_item_order_whole_and_splits_single_rules() -> None:
    rows = [
        _row("1", "a", color="黑色", size="S"),
        _row("2", "b", color="白色", size="3XL"),
        _row("3", "c", composition=3),
        _row("4", "c", composition=3, color="白色"),
        _row("5", "d", style="base-b"),
    ]
    details = {
        "1": _detail("A面"),
        "2": _detail("B面"),
        "3": _detail("A面", "B面"),
        "4": _detail("A面", "B面"),
        "5": _detail("A面"),
    }

    groups = plan_completed_haloo_batches(rows, details)

    assert any(group.item_ids == ("3", "4") for group in groups)
    assert any(group.color == "黑色" and group.size_group == "S-XL" for group in groups)
    assert any(group.color == "白色" and group.size_group == "2XL-5XL" for group in groups)
    assert not any("5" in group.item_ids for group in groups)


def test_completed_request_is_blocked_until_non_reopening_is_verified() -> None:
    group = plan_completed_haloo_batches(
        [_row("1", "a")], {"1": _detail("A面")}
    )[0]
    with pytest.raises(RuntimeError, match="重开生产"):
        completed_batch_request(group, 12)
    assert completed_batch_request(
        group, 12, verified_non_reopening=True
    ) == {
        "production_order_item_ids": ["1"],
        "batch_creat_type": 2,
        "batch_rule_id": 12,
    }


def test_non_completed_snapshot_is_rejected() -> None:
    row = _row("1", "a")
    row["status"] = 5
    with pytest.raises(RuntimeError, match="非“已生产”"):
        plan_completed_haloo_batches([row], {"1": _detail("A面")})

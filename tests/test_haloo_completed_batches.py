import pytest
from unittest.mock import patch

from automatic_print.automation.batches.classification import (
    BACK_FACE,
    DOUBLE_FACE_DETAIL,
    FRONT_FACE,
    UNKNOWN_FACE_DETAIL,
    classify_production_face,
    size_band,
)
from automatic_print.automation.batches.supplements.completed import (
    completed_batch_request,
    plan_completed_erp_batches,
)
from automatic_print.automation.batches.supplements.completed import (
    _confirmed_group_codes, generate_completed_groups, verify_completed_group,
)
from automatic_print.automation.api.erp.items import (
    generate_selected_batch,
    generate_supplement_batch,
)


def _row(item, order, *, composition=1, style="base-a", color="黑色", size="M"):
    return {
        "id": item,
        "order_id": order,
        "status": 9,
        "order_composition": composition,
        "qty": 1,
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


def test_completed_plan_keeps_multi_item_order_whole_and_splits_logistics_style_color() -> None:
    rows = [
        _row("1", "a", color="黑色", size="S"),
        _row("2", "b", color="白色", size="3XL"),
        _row("3", "c", composition=3),
        _row("4", "c", composition=3, color="白色"),
        _row("5", "d", style="base-b"),
        _row("6", "e"),
    ]
    details = {
        "1": _detail("A面"),
        "2": _detail("B面"),
        "3": _detail("A面", "B面"),
        "4": _detail("A面", "B面"),
        "5": _detail("A面"),
        "6": _detail("A面"),
    }
    rows[-1]["logistics_sorting_code"] = "GOFO"

    groups = plan_completed_erp_batches(rows, details)

    assert any(group.item_ids == ("3", "4") for group in groups)
    assert any(group.color == "黑色" and group.size_group == "S-XL" for group in groups)
    assert any(group.color == "白色" and group.size_group == "2XL-5XL" for group in groups)
    assert any(group.item_ids == ("5",) and group.style_id == "base-b" for group in groups)
    assert any(group.item_ids == ("6",) and group.logistics_code == "GOFO" for group in groups)
    assert not any({"1", "5"} <= set(group.item_ids) for group in groups)


def test_completed_request_uses_exact_supplement_item_quantities() -> None:
    group = plan_completed_erp_batches(
        [_row("1", "a")], {"1": _detail("A面")}
    )[0]
    assert completed_batch_request(group, 12) == {
        "item_list": [{"item_id": "1", "qty": 1}],
        "batch_rule_id": 12,
    }


def test_multi_item_order_cannot_split_on_conflicting_logistics() -> None:
    rows = [_row("1", "same", composition=3), _row("2", "same", composition=3)]
    rows[1]["logistics_sorting_code"] = "GOFO"
    with pytest.raises(RuntimeError, match="同订单的物流"):
        plan_completed_erp_batches(
            rows, {"1": _detail("A面"), "2": _detail("A面")}
        )


def test_selected_batch_generation_calls_exact_id_endpoint() -> None:
    with patch(
        "automatic_print.automation.api.erp.items.call_module",
        return_value={"code": "batch"},
    ) as call:
        result = generate_selected_batch(object(), ["1", 2], 12)

    assert result == {"code": "batch"}
    assert call.call_args.args[3] == {
        "production_order_item_ids": ["1", "2"],
        "batch_creat_type": 2,
        "batch_rule_id": 12,
    }


def test_supplement_batch_generation_calls_exact_item_quantities() -> None:
    with patch(
        "automatic_print.automation.api.erp.items.call_module",
        return_value={"code": "batch"},
    ) as call:
        result = generate_supplement_batch(object(), [("1", 1)], "1")

    assert result == {"code": "batch"}
    assert call.call_args.args[1:] == (
        "productItemManage-",
        "v",
        {"item_list": [{"item_id": "1", "qty": 1}], "batch_rule_id": "1"},
        "productItemManage-ppzeq-54.js",
    )


def test_non_completed_snapshot_is_rejected() -> None:
    row = _row("1", "a")
    row["status"] = 5
    with pytest.raises(RuntimeError, match="其他订单状态"):
        plan_completed_erp_batches([row], {"1": _detail("A面")})


def test_production_and_completed_sources_share_the_same_grouping_strategy() -> None:
    rows = [_row("1", "a", composition=3), _row("2", "a", composition=3),
            _row("3", "b", color="白色")]
    details = {row["id"]: _detail("A面") for row in rows}
    completed = plan_completed_erp_batches(rows, details)
    for row in rows:
        row["status"] = 5
    production = plan_completed_erp_batches(rows, details, source_status=5)
    assert [(group.item_ids, group.logistics_code, group.order_composition,
             group.face, group.style_id, group.color, group.size_group)
            for group in production] == [
            (group.item_ids, group.logistics_code, group.order_composition,
             group.face, group.style_id, group.color, group.size_group)
            for group in completed]
    assert {group.source_status for group in production} == {5}


def test_multi_item_orders_do_not_split_by_style_or_color() -> None:
    rows = [_row("1", "a", composition=3), _row("2", "a", composition=3),
            _row("3", "b", composition=3, style="base-b", color="白色"),
            _row("4", "b", composition=3, style="base-b", color="白色")]
    details = {row["id"]: _detail("A面") for row in rows}
    groups = plan_completed_erp_batches(rows, details)
    assert len(groups) == 1
    assert set(groups[0].item_ids) == {"1", "2", "3", "4"}
    assert groups[0].style_id == groups[0].color == ""


def test_mixed_style_order_stays_whole() -> None:
    rows = [_row("1", "a", composition=3),
            _row("2", "a", composition=3, style="base-b")]
    groups = plan_completed_erp_batches(rows, {"1": _detail("A面"), "2": _detail("A面")})
    assert len(groups) == 1
    assert groups[0].style_name == ""
    assert groups[0].item_ids == ("1", "2")


def test_single_item_same_style_splits_black_and_white() -> None:
    rows = [_row("1", "a", style="base-a", color="黑色"),
            _row("2", "b", style="base-a", color="白色"),
            _row("3", "c", style="base-b", color="黑色")]
    groups = plan_completed_erp_batches(
        rows, {row["id"]: _detail("A面") for row in rows})
    assert {(group.style_id, group.color): group.item_ids for group in groups} == {
        ("base-a", "黑色"): ("1",),
        ("base-a", "白色"): ("2",),
        ("base-b", "黑色"): ("3",),
    }


def test_longfeng_completed_plan_matches_logistics_style_and_color_rules() -> None:
    single_multi_usps = _row("1", "single-multi-usps", composition=2)
    single_multi_usps["qty"] = 3
    single_multi_gofo = _row("2", "single-multi-gofo", composition=2)
    single_multi_gofo["qty"] = 2
    single_multi_gofo["logistics_sorting_code"] = "GOFO"
    rows = [
        single_multi_usps,
        single_multi_gofo,
        _row("3", "multi-a", composition=3, style="base-a", color="黑色"),
        _row("4", "multi-a", composition=3, style="base-b", color="白色"),
        _row("5", "single-black", style="base-a", color="黑色"),
        _row("6", "single-white", style="base-a", color="白色"),
        _row("7", "single-other-style", style="base-b", color="黑色"),
    ]
    details = {row["id"]: _detail("A面") for row in rows}

    groups = plan_completed_erp_batches(rows, details)

    assert {(group.logistics_code, group.order_composition): group.item_ids
            for group in groups if group.order_composition == "单项多件"} == {
        ("GOFO", "单项多件"): ("2",),
        ("USPS", "单项多件"): ("1",),
    }
    multi = next(group for group in groups if group.order_composition == "多项多件")
    assert multi.item_ids == ("3", "4")
    assert multi.style_id == multi.color == ""
    singles = {(group.style_id, group.color): group.item_ids for group in groups
               if group.order_composition == "单项单件"}
    assert singles == {
        ("base-a", "黑色"): ("5",),
        ("base-a", "白色"): ("6",),
        ("base-b", "黑色"): ("7",),
    }


def test_longfeng_confirmed_strategy_ignores_logistics_style_and_size() -> None:
    rows = [
        _row("1", "black-a", style="base-a", color="黑色", size="S"),
        _row("2", "black-b", style="base-b", color="黑色", size="4XL"),
        _row("3", "white", style="base-a", color="白色", size="3XL"),
        _row("4", "double-a", style="base-a", color="黑色", size="S"),
        _row("5", "double-b", style="base-b", color="白色", size="5XL"),
        _row("6", "multi-a", composition=3),
        _row("7", "multi-a", composition=3, color="白色"),
        _row("8", "multi-b", composition=3),
    ]
    for row in rows:
        row["process_route_code"] = "A00"
    for row in (rows[1], rows[4], rows[7]):
        row["logistics_sorting_code"] = "GOFO"
    details = {row["id"]: _detail("A面") for row in rows}
    details["4"] = details["5"] = _detail("A面", "B面")

    groups = plan_completed_erp_batches(rows, details, platform_name="隆丰")

    assert {group.logistics_code for group in groups} == {""}
    assert {group.item_ids for group in groups} == {
        ("1", "2"), ("3",), ("4", "5"), ("6", "7", "8")
    }
    assert all(not group.style_id and not group.size_group for group in groups)
    assert next(group for group in groups if group.item_ids == ("4", "5")).color == ""


def test_haloo_confirmed_strategy_uses_logistics_face_color_and_size_band() -> None:
    rows = [
        _row("1", "black-small", style="base-a", color="黑色", size="S"),
        _row("2", "black-large", style="base-b", color="黑色", size="3XL"),
        _row("3", "other-a", color="红色", size="S"),
        _row("4", "other-b", color="蓝色", size="5XL"),
        _row("5", "double-a", color="黑色"),
        _row("6", "double-b", color="白色"),
        _row("7", "multi-a", composition=3),
        _row("8", "multi-a", composition=3, color="白色"),
    ]
    details = {row["id"]: _detail("A面") for row in rows}
    details["5"] = details["6"] = _detail("A面", "B面")

    groups = plan_completed_erp_batches(rows, details, platform_name="Haloo")

    assert {group.item_ids for group in groups} == {
        ("1",), ("2",), ("3", "4"), ("5", "6"), ("7", "8")
    }
    mixed = next(group for group in groups if group.item_ids == ("3", "4"))
    assert (mixed.color, mixed.size_group) == ("混色", "")
    double = next(group for group in groups if group.item_ids == ("5", "6"))
    assert double.face == "双面" and not double.color
    multi = next(group for group in groups if group.item_ids == ("7", "8"))
    assert multi.face == "不区分面别"


@pytest.mark.parametrize("field,value,message", [
    ("color", "", "缺少颜色"),
    ("detail", _detail("袖口"), "缺少可识别"),
])
def test_confirmed_strategy_rejects_unknown_single_fields(field, value, message) -> None:
    row = _row("1", "a")
    row["process_route_code"] = "A00"
    detail = _detail("A面")
    if field == "detail":
        detail = value
    else:
        row[field] = value
    with pytest.raises(RuntimeError, match=message):
        plan_completed_erp_batches(
            [row], {"1": detail}, platform_name="隆丰"
        )


def test_generation_rechecks_whole_order_and_confirms_one_code() -> None:
    row = _row("1", "a")
    row["production_batch_code"] = "original"
    group = plan_completed_erp_batches([row], {"1": _detail("A面")})[0]
    after = {**row, "supplement_detail_list": [{"production_batch_code": "new"}]}
    page = object()
    with patch("automatic_print.automation.batches.supplements.completed.list_batch_rules",
               return_value=[type("Rule", (), {"id": 1})()]), \
             patch("automatic_print.automation.api.erp.items.list_production_items",
               side_effect=[{"list": [row], "total": 1}, {"list": [after], "total": 1}]), \
         patch("automatic_print.automation.batches.supplements.completed.production_item_images",
               return_value=_detail("A面")), \
         patch("automatic_print.automation.batches.supplements.completed.generate_supplement_batch") as write:
        assert generate_completed_groups(page, (group,), 1) == ("new",)
    write.assert_called_once_with(page, [("1", 1)], 1)


def test_generation_accepts_platform_split_into_one_code_per_order() -> None:
    rows = [_row("1", "a", composition=2), _row("2", "b", composition=2)]
    group = plan_completed_erp_batches(
        rows, {"1": _detail("A面"), "2": _detail("A面")}
    )[0]
    after_a = {**rows[0], "supplement_detail_list": [
        {"production_batch_code": "new-a"}]}
    after_b = {**rows[1], "supplement_detail_list": [
        {"production_batch_code": "new-b"}]}
    with patch("automatic_print.automation.batches.supplements.completed.list_batch_rules",
               return_value=[type("Rule", (), {"id": 1})()]), \
         patch("automatic_print.automation.api.erp.items.list_production_items",
               side_effect=[
                   {"list": [rows[0]], "total": 1},
                   {"list": [rows[1]], "total": 1},
                   {"list": [after_a], "total": 1},
                   {"list": [after_b], "total": 1},
               ]), \
         patch("automatic_print.automation.batches.supplements.completed.production_item_images",
               return_value=_detail("A面")), \
         patch("automatic_print.automation.batches.supplements.completed.generate_supplement_batch"):
        assert generate_completed_groups(object(), (group,), 1) == ("new-a", "new-b")


def test_generation_confirmation_requires_every_item_to_have_one_code() -> None:
    rows = [_row("1", "a", composition=3), _row("2", "a", composition=3)]
    group = plan_completed_erp_batches(
        rows, {"1": _detail("A面"), "2": _detail("A面")}
    )[0]
    confirmed = {
        **rows[0], "supplement_detail_list": [{"production_batch_code": "new"}]
    }
    with patch(
        "automatic_print.automation.batches.supplements.completed._whole_order",
        return_value=[confirmed, rows[1]],
    ), pytest.raises(RuntimeError, match="未确认或多重归属"):
        _confirmed_group_codes(object(), group)


def test_generation_rejects_partial_order_before_write() -> None:
    rows = [_row("1", "a", composition=3), _row("2", "a", composition=3)]
    group = plan_completed_erp_batches(rows, {"1": _detail("A面"), "2": _detail("A面")})[0]
    with patch("automatic_print.automation.api.erp.items.list_production_items",
               return_value={"list": rows[:1], "total": 2}):
        with pytest.raises(RuntimeError, match="未完整返回"):
            verify_completed_group(object(), group)


def test_generation_rejects_existing_supplement() -> None:
    row = _row("1", "a")
    group = plan_completed_erp_batches([row], {"1": _detail("A面")})[0]
    row["supplement_detail_list"] = [{"production_batch_code": "old"}]
    with patch("automatic_print.automation.api.erp.items.list_production_items",
               return_value={"list": [row], "total": 1}), \
         patch("automatic_print.automation.batches.supplements.completed.production_item_images",
               return_value=_detail("A面")):
        with pytest.raises(RuntimeError, match="已有补单"):
            verify_completed_group(object(), group)

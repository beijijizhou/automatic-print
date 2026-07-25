import pytest

from automatic_print.automation.batch_classification import (
    DOUBLE_FACE,
    SINGLE_FACE,
    UNKNOWN_FACE,
    classify_order_composition,
    composition_filter,
    detailed_compositions,
)
from automatic_print.automation.rule_batches import (
    RuleBatchItem,
    _generate_filtered_batch_api,
    _preview_plan_from_api,
)


class Platform:
    name = "测试平台"
    shipping_categories = ("UPS",)
    order_compositions = ("单项单件", "单项多件", "多项多件")

    @staticmethod
    def shipping_filter_value(_name):
        return "UPS_CODE"


def test_single_piece_is_split_by_erp_view_count() -> None:
    assert classify_order_composition(
        {"order_composition": 1, "view_count": 1}
    ) == SINGLE_FACE
    assert classify_order_composition(
        {"order_composition": 1, "view_count": 2}
    ) == DOUBLE_FACE
    assert classify_order_composition(
        {"order_composition": 1}
    ) == UNKNOWN_FACE


def test_detailed_compositions_adds_separate_double_face_batch() -> None:
    assert detailed_compositions(
        ("单项单件", "单项多件", "多项多件")
    ) == (
        SINGLE_FACE,
        DOUBLE_FACE,
        "单项多件",
        "多项多件",
    )


def test_double_face_filter_uses_view_count_two() -> None:
    assert composition_filter(SINGLE_FACE) == ("1", 1)
    assert composition_filter(DOUBLE_FACE) == ("1", 2)
    with pytest.raises(ValueError):
        composition_filter(UNKNOWN_FACE)


def test_unknown_face_is_left_unmatched_for_safety(monkeypatch) -> None:
    rows = [
        {"logistics_sorting_code": "UPS_CODE", "order_composition": 1},
        {
            "logistics_sorting_code": "UPS_CODE",
            "order_composition": 1,
            "view_count": 2,
        },
    ]
    monkeypatch.setattr(
        "automatic_print.automation.rule_batches._load_all_received_rows",
        lambda _page: (rows, 2),
    )

    plan = _preview_plan_from_api(None, Platform(), lambda _text: None)

    assert plan.total_items == 1
    assert plan.received_count == 2


def test_generation_payload_filters_double_face(monkeypatch) -> None:
    captured = {}

    def list_items(_page, payload):
        captured.update(payload)
        return {"total": 1}

    monkeypatch.setattr(
        "automatic_print.automation.rule_batches.list_production_items",
        list_items,
    )
    monkeypatch.setattr(
        "automatic_print.automation.rule_batches.generate_filtered_batch",
        lambda *_args: None,
    )

    _generate_filtered_batch_api(
        None,
        RuleBatchItem("UPS", DOUBLE_FACE, 1),
        Platform(),
        99,
    )

    assert captured["order_compositions"] == ["1"]
    assert captured["view_count"] == 2

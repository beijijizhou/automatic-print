import pytest

from automatic_print.automation.longfeng import BatchPreview, ShippingBatchPlan
from automatic_print.automation.platforms import get_erp_platform
from automatic_print.automation.rule_batches import (
    RuleBatchItem,
    RuleBatchPlan,
)


def test_batch_preview_confirmation_is_explicit() -> None:
    preview = BatchPreview(
        client="隆丰",
        shipping_method="USPS",
        order_composition="单项单件",
        result_count=25,
        page_url="https://example.test",
    )

    assert preview.confirmation_text == "隆丰 / USPS / 单项单件 / 25 个生产项"


def test_shipping_plan_splits_cbt_from_all_received_items() -> None:
    plan = ShippingBatchPlan.from_counts(total_count=577, cbt_count=77)

    assert plan.non_cbt_count == 500
    assert plan.confirmation_text == (
        "隆丰已接单共 577 个生产项：CBT 77 个，非 CBT 500 个"
    )


def test_shipping_plan_rejects_impossible_counts() -> None:
    with pytest.raises(ValueError):
        ShippingBatchPlan.from_counts(total_count=10, cbt_count=11)


def test_haloo_batch_rules_prioritize_shipping_then_composition() -> None:
    platform = get_erp_platform("Haloo")

    assert platform.shipping_categories == (
        "UPS",
        "FedEx",
        "SWIFT",
        "USPS",
        "GOFO",
        "Yanwen",
    )
    assert "CBT" not in platform.shipping_categories
    assert platform.order_compositions == (
        "单项单件",
        "单项多件",
        "多项多件",
    )
    assert platform.shipping_filter_value("SWIFT") == "SWIF"
    assert platform.shipping_filter_value("Yanwen") == "YANW"
    assert platform.excluded_shipping_categories == ("SPEE",)


def test_cbt_rules_belong_only_to_longfeng() -> None:
    assert get_erp_platform("隆丰").shipping_categories == (
        "CBT",
        "非 CBT",
    )


def test_rule_batch_plan_counts_only_nonempty_categories() -> None:
    plan = RuleBatchPlan(
        "Haloo",
        (
            RuleBatchItem("UPS", "单项单件", 12),
            RuleBatchItem("UPS", "单项多件", 0),
            RuleBatchItem("FedEx", "单项单件", 8),
        ),
        20,
    )

    assert plan.total_items == 20
    assert len(plan.nonempty_items) == 2


def test_rule_batch_plan_counts_explicit_logistics_exclusions() -> None:
    plan = RuleBatchPlan(
        "Haloo",
        (RuleBatchItem("UPS", "单项单件", 20),),
        22,
        (RuleBatchItem("SPEE", "不生成", 2),),
    )

    assert plan.excluded_count == 2
    assert plan.total_items + plan.excluded_count == plan.received_count

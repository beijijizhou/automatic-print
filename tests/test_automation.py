import pytest

from automatic_print.automation.longfeng import BatchPreview, ShippingBatchPlan


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

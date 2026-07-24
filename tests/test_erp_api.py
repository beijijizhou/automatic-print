from automatic_print.automation.erp_api import (
    batch_page_payload,
    production_item_payload,
)


def test_production_item_payload_uses_api_filters() -> None:
    payload = production_item_payload(
        shipping_codes=("SPEE",),
        order_compositions=("1",),
    )

    assert payload["status"] == ["1"]
    assert payload["logistics_sorting_code_list"] == ["SPEE"]
    assert payload["order_compositions"] == ["1"]
    assert payload["page_size"] == 200


def test_batch_page_payload_requests_production_batches() -> None:
    payload = batch_page_payload(page=2)

    assert payload["product_sale_type_list"] == [1]
    assert payload["initial_status"] == 1
    assert payload["page"] == 2
    assert payload["page_size"] == 20

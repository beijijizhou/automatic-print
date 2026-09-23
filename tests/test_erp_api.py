from automatic_print.automation.api.erp import (
    batch_page_payload,
    production_item_payload,
)
from automatic_print.automation.api.erp.gateway import (
    CHUNK_ROOT,
    call_imported_module,
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


def test_hashed_module_can_be_resolved_from_stable_importer() -> None:
    class Frame:
        name = "fnsz-sale"

        def evaluate(self, script, argument):
            assert "new URL(match[2], importer)" in script
            assert argument == {
                "importerPrefix": "GlobalBuildBatch.vue_",
                "marker": "product_sale_type_list",
                "exportName": "k",
                "argument": {"product_sale_type_list": 1},
                "fallback": CHUNK_ROOT + "index-current.js",
            }
            return [{"id": 1}]

    page = type("Page", (), {"frames": [Frame()]})()
    assert call_imported_module(
        page, "GlobalBuildBatch.vue_", "product_sale_type_list", "k",
        {"product_sale_type_list": 1}, "index-current.js",
    ) == [{"id": 1}]

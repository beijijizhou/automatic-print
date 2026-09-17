from types import SimpleNamespace

from automatic_print.automation.api.s2b.metadata.prepare import prepare_s2b_metadata
from automatic_print.automation.api.s2b.metadata.store import (
    color_for_path,
    order_for_path,
    register_batch_records,
)


def s2b_image(tmp_path):
    root = tmp_path / "AS2B014Mt______1_22UJ9KT4VCZA_20260917_014406_cachetest"
    image = root / "S" / "22UJ9KT4VCZA-1-1-ORDER7-1-1-1-1-棉-S.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"first")
    return image


def payload(color="蓝色"):
    return {
        "batch_number": "22UJ9KT4VCZA",
        "records": [{
            "order_code": "ORDER7",
            "order_item_code": "ORDER7-1",
            "color": color,
            "size": "S",
        }],
    }


def test_replaced_file_at_same_path_invalidates_order_and_color(tmp_path):
    image = s2b_image(tmp_path)
    register_batch_records([image], payload())
    assert color_for_path(image) == "蓝色"
    assert order_for_path(image) == "ORDER7"

    image.write_bytes(b"replacement-is-a-different-file")

    assert color_for_path(image) is None
    assert order_for_path(image) is None


def test_complete_memory_cache_does_not_require_gateway_config(tmp_path, monkeypatch):
    image = s2b_image(tmp_path)
    register_batch_records([image], payload("黑色"))
    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.prepare.gateway_config",
        lambda: (_ for _ in ()).throw(AssertionError("cache should avoid gateway config")),
    )

    records = prepare_s2b_metadata([image], SimpleNamespace())

    assert records[0]["colors"] == {"黑色": 1}
    assert records[0]["matched_images"] == 1

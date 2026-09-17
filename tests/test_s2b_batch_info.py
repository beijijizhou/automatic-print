from types import SimpleNamespace

import pytest

from automatic_print.automation.api.s2b.metadata.batch_name import (
    find_s2b_batch_folder,
    parse_s2b_batch_name,
)
from automatic_print.automation.api.s2b.metadata.store import (
    color_for_path,
    order_for_path,
    register_batch_records,
    register_path_aliases,
)
from automatic_print.automation.api.s2b.metadata.prepare import (
    metadata_summary_text,
    prepare_s2b_metadata,
)


def test_batch_name_is_parsed_from_stable_right_hand_fields():
    parsed = parse_s2b_batch_name(
        "LNS2B004Sg_b_S_XL_SP___352_YRJ9ZFJYTUUA_20260913_181525_kysji69n"
    )
    assert parsed.batch_number == "YRJ9ZFJYTUUA"
    assert parsed.expected_count == 352
    assert parsed.exported_date == "20260913"


def test_supplement_batch_without_count_uses_right_hand_batch_identity():
    parsed = parse_s2b_batch_name(
        "【补单】202608300008_IW6J3TIZUQ8K_20260831_035112_rpkaxw42"
    )
    assert parsed.batch_number == "IW6J3TIZUQ8K"
    assert parsed.expected_count == 0


def test_batch_folder_is_found_above_size_and_image(tmp_path):
    root = tmp_path / "LNS2B017Sg_b__SP___222_26OP3LGLUEUV_20260916_010042_5unwyr1p"
    image = root / "S" / "26OP3LGLUEUV-1-1-2TB3P5-1-1-1-222-棉-S.png"
    image.parent.mkdir(parents=True)
    image.touch()
    assert find_s2b_batch_folder(image).batch_number == "26OP3LGLUEUV"


def test_api_color_matches_s2b_order_item_and_size(tmp_path):
    root = tmp_path / "LNS2B017Sg_b__SP___1_26OP3LGLUEUV_20260916_010042_5unwyr1p"
    image = root / "S" / "26OP3LGLUEUV-1-1-2TB3P5-1-1-1-1-棉-S.png"
    image.parent.mkdir(parents=True)
    image.touch()
    count = register_batch_records([image], {
        "batch_number": "26OP3LGLUEUV",
        "records": [{
            "order_code": "2TB3P5",
            "order_item_code": "2TB3P5-1",
            "color": "黑色",
            "size": "S",
        }],
    })
    assert count == 1
    assert color_for_path(image) == "黑色"


def test_prepared_gap_copy_keeps_api_order_and_color(tmp_path):
    root = tmp_path / "AS2B014Mt______1_22UJ9KT4VCZA_20260917_014406_ucjfsdyh"
    image = root / "S" / "22UJ9KT4VCZA-1-1-ORDER7-1-1-1-1-棉-S.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"source")
    prepared = tmp_path / "cache" / image.name
    prepared.parent.mkdir()
    prepared.write_bytes(b"prepared")
    register_batch_records([image], {
        "batch_number": "22UJ9KT4VCZA",
        "records": [{
            "order_code": "ORDER7", "order_item_code": "ORDER7-1",
            "color": "黑色", "size": "S",
        }],
    })

    register_path_aliases({str(image.resolve()): str(prepared.resolve())})

    assert color_for_path(prepared) == "黑色"
    assert order_for_path(prepared) == "ORDER7"


def test_api_order_and_color_fall_back_to_unique_order_folder(tmp_path):
    root = tmp_path / "AS2B014Mt______1_22UJ9KT4VCZA_20260917_014406_ucjfsdyh"
    image = root / "ORDER7" / "S" / "unrecognizable.png"
    image.parent.mkdir(parents=True)
    image.touch()
    count = register_batch_records([image], {
        "batch_number": "22UJ9KT4VCZA",
        "records": [{
            "order_code": "ORDER7",
            "order_item_code": "ORDER7-1",
            "color": "蓝色",
            "size": "S",
        }],
    })
    from automatic_print.layout_engine.orders.order_groups import order_key
    assert count == 1
    assert color_for_path(image) == "蓝色"
    assert order_for_path(image) == "ORDER7"
    assert order_key(image) == "order7"


def test_order_folder_fallback_refuses_ambiguous_folder(tmp_path):
    root = tmp_path / "AS2B014Mt______1_22UJ9KT4VCZA_20260917_014406_ucjfsdyh"
    image = root / "ORDER7_ORDER8" / "S" / "unrecognizable.png"
    image.parent.mkdir(parents=True)
    image.touch()
    count = register_batch_records([image], {
        "batch_number": "22UJ9KT4VCZA",
        "records": [
            {"order_code": "ORDER7", "color": "蓝色", "size": "S"},
            {"order_code": "ORDER8", "color": "黑色", "size": "S"},
        ],
    })
    assert count == 0
    assert color_for_path(image) is None
    assert order_for_path(image) is None


def test_detected_s2b_always_fetches_color_without_developer_mode(
    tmp_path, monkeypatch
):
    root = tmp_path / "AS2B014Mt______1_22UJ9KT4VCZA_20260917_014406_ucjfsdyh"
    image = root / "S" / "22UJ9KT4VCZA-1-1-ORDER7-1-1-1-1-棉-S.png"
    image.parent.mkdir(parents=True)
    image.touch()
    calls = []
    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.prepare.gateway_config",
        lambda: ("https://example.test", "key"),
    )

    def fetch(batch_number):
        calls.append(batch_number)
        return {
            "batch_number": batch_number,
            "source_total": 1,
            "records": [{
                "order_code": "ORDER7",
                "order_item_code": "ORDER7-1",
                "color": "蓝色",
                "size": "S",
            }],
        }

    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.prepare.fetch_s2b_batch_info", fetch
    )
    result = prepare_s2b_metadata(
        [image],
        SimpleNamespace(s2b_batch_api_enabled=False, platform_name=""),
    )
    cached = prepare_s2b_metadata([image], SimpleNamespace())
    assert calls == ["22UJ9KT4VCZA"]
    assert result[0]["colors"] == {"蓝色": 1}
    assert cached[0]["colors"] == {"蓝色": 1}
    assert cached[0]["matched_images"] == 1
    assert "颜色：蓝色1张" in metadata_summary_text(cached)


def test_detected_s2b_reports_unmatched_color_and_keeps_running(
    tmp_path, monkeypatch
):
    root = tmp_path / "AS2B014Mt______1_22UJ9KT4VCZA_20260917_014406_ucjfsdyh"
    image = root / "S" / "22UJ9KT4VCZA-1-1-UNKNOWN-1-1-1-1-棉-S.png"
    image.parent.mkdir(parents=True)
    image.touch()
    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.prepare.gateway_config",
        lambda: ("https://example.test", "key"),
    )
    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.prepare.fetch_s2b_batch_info",
        lambda batch_number: {
            "batch_number": batch_number,
            "records": [{
                "order_code": "OTHER",
                "order_item_code": "OTHER-1",
                "color": "黑色",
                "size": "S",
            }],
        },
    )
    result = prepare_s2b_metadata([image], SimpleNamespace())
    assert result[0]["matched_images"] == 0
    assert result[0]["unmatched_files"] == [image.name]
    assert "继续排版" in result[0]["warning"]


def test_non_s2b_batch_does_not_require_color_service(tmp_path, monkeypatch):
    image = tmp_path / "ordinary" / "S" / "ORDER-1.png"
    image.parent.mkdir(parents=True)
    image.touch()
    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.prepare.gateway_config",
        lambda: pytest.fail("non-S2B input must not access the gateway"),
    )
    assert prepare_s2b_metadata([image], SimpleNamespace()) == []


def test_missing_service_reports_choice_instead_of_stopping(tmp_path, monkeypatch):
    root = tmp_path / "AS2B014Mt______1_22UJ9KT4VCZA_20260917_014406_ucjfsdyh"
    image = root / "S" / "unrecognizable.png"
    image.parent.mkdir(parents=True)
    image.touch()
    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.prepare.gateway_config",
        lambda: ("", ""),
    )
    result = prepare_s2b_metadata([image], SimpleNamespace())
    assert len(result) == 1
    assert result[0]["matched_images"] == 0
    assert "继续排版" in result[0]["warning"]
    assert "用户确认" in result[0]["warning"]

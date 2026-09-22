from types import SimpleNamespace

import pytest

from automatic_print.automation.api.s2b.metadata.batch_name import (
    find_s2b_batch_folder,
    image_batch_number,
    parse_s2b_batch_name,
    parse_s2b_image_name,
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


def test_mixed_underscore_exports_match_each_embedded_batch_and_item(tmp_path, monkeypatch):
    root = tmp_path / "HS2B011Mt______20_KU7S5B8XMFDW_20260919_232509_qkgzot2a"
    first = root / "5OIT77_1_6_1_6_棉_M_KU7S5B8XMFDW-4_1.png"
    second = root / "K3ELXV_1_1_2_6_棉_XL_X64RYCOFJJPJ-5_3.png"
    wrong_item = root / "5OIT77_2_6_1_6_棉_M_KU7S5B8XMFDW-4_2.png"
    root.mkdir()
    for path in (first, second, wrong_item):
        path.touch()
    assert image_batch_number(first) == "KU7S5B8XMFDW"
    assert image_batch_number(second) == "X64RYCOFJJPJ"
    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.prepare.gateway_config",
        lambda: ("https://example.test", "key"),
    )
    calls = []

    def fetch(batch):
        calls.append(batch)
        records = {
            "KU7S5B8XMFDW": [
                {"order_code": "5OIT77", "order_item_code": "5OIT77-1",
                 "color": "白色", "size": "M"},
            ],
            "X64RYCOFJJPJ": [
                {"order_code": "K3ELXV", "order_item_code": "K3ELXV-1",
                 "color": "黑色", "size": "XL"},
            ],
        }
        return {"batch_number": batch, "records": records[batch]}

    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.prepare.fetch_s2b_batch_info", fetch,
    )
    result = prepare_s2b_metadata([first, second, wrong_item], SimpleNamespace())
    assert calls == ["KU7S5B8XMFDW", "X64RYCOFJJPJ"]
    assert [record["matched_images"] for record in result] == [1, 1]
    assert color_for_path(first) == "白色"
    assert color_for_path(second) == "黑色"
    assert color_for_path(wrong_item) is None


def test_hyphen_export_in_batch_root_matches_exact_item_and_size(tmp_path):
    root = tmp_path / "CYS2B001Mt______3_8EIMH54LNIIL_20260919_185954_hr08uhzo"
    first = root / "8EIMH54LNIIL-1-1-E4G3AP-4-2-1-140-棉-3XL.png"
    second = root / "8EIMH54LNIIL-1-9-E4G3AP-5-2-1-140-棉-4XL.png"
    root.mkdir()
    for path in (first, second):
        path.touch()
    payload = {"batch_number": "8EIMH54LNIIL", "records": [
        {"order_code": "E4G3AP", "order_item_code": "E4G3AP-4",
         "size": "3XL", "color": "黑色"},
        {"order_code": "E4G3AP", "order_item_code": "E4G3AP-5",
         "size": "4XL", "color": "白色"},
    ]}
    assert register_batch_records([first, second], payload) == 2
    assert color_for_path(first) == "黑色"
    assert color_for_path(second) == "白色"
    from automatic_print.layout_engine.orders.order_groups import order_key
    from automatic_print.layout_engine.intake.metadata.source_metadata import source_size
    assert [order_key(path) for path in (first, second)] == ["e4g3ap"] * 2
    assert [source_size(path) for path in (first, second)] == ["3XL", "4XL"]


def test_filename_size_wins_over_misleading_size_folder(tmp_path):
    root = tmp_path / "HS2B010Sg_Clr_____31_9DAL9VRKA8LN_20260919_231223_w31kryif"
    prefixed = root / "5XL" / "3XL_9DAL9VRKA8LN-1-1-7CYTDQ-1-1-1-31-棉.png"
    suffixed = root / "4XL" / "9DAL9VRKA8LN-17-4-E2WSGC-1-1-1-31-棉-L.png"
    for path in (prefixed, suffixed):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    from automatic_print.layout_engine.intake.metadata.source_metadata import source_size
    assert [source_size(path) for path in (prefixed, suffixed)] == ["3XL", "L"]
    assert register_batch_records([prefixed, suffixed], {
        "batch_number": "9DAL9VRKA8LN", "records": [
            {"order_code": "7CYTDQ", "order_item_code": "7CYTDQ-1",
             "size": "3XL", "color": "白色"},
            {"order_code": "E2WSGC", "order_item_code": "E2WSGC-1",
             "size": "L", "color": "蓝色"},
        ],
    }) == 2


def test_partial_folder_uses_batch_code_from_image(tmp_path, monkeypatch):
    root = tmp_path / "H S2B016Sg______19"
    image = root / "3XL_4JFHMUQ8ZKCV-1-1-INQIHJ-1-1-1-19-棉.png"
    root.mkdir()
    image.touch()
    parsed = find_s2b_batch_folder(image)
    assert parsed.expected_count == 19
    assert parsed.batch_number == ""
    assert image_batch_number(image) == "4JFHMUQ8ZKCV"
    assert parse_s2b_image_name(image).order_item_code == "INQIHJ-1"
    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.prepare.gateway_config",
        lambda: ("https://example.test", "key"),
    )
    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.prepare.fetch_s2b_batch_info",
        lambda code: {"batch_number": code, "source_total": 19, "records": [
            {"order_code": "INQIHJ", "order_item_code": "INQIHJ-1",
             "size": "3XL", "color": "黑色"},
        ]},
    )
    result = prepare_s2b_metadata([image], SimpleNamespace())
    assert result[0]["batch_number"] == "4JFHMUQ8ZKCV"
    assert result[0]["folder_count"] == 19
    assert result[0]["matched_images"] == 1


def test_reordered_partial_folder_and_mixed_hyphen_batches(tmp_path, monkeypatch):
    root = tmp_path / "22_IRORKWQ8MKHZ_20260921_021712_kuqfwpqv_HS2B018Sg______50"
    image = root / "L_IRORKWQ8MKHZ-1-1-7AFYK3-1-1-1-22-棉.png"
    root.mkdir()
    image.touch()
    assert find_s2b_batch_folder(image).expected_count == 50
    assert image_batch_number(image) == "IRORKWQ8MKHZ"
    from automatic_print.layout_engine.intake.metadata.source_metadata import source_size
    assert source_size(image) == "L"

    mixed_root = tmp_path / "HS2B016Sg______12_PBDUHXTM9NQ9_20260921_012009_mdboi3c7"
    second = mixed_root / "S_OGNWD9UB7QR3-1-1-ORDER8-1-1-1-1-棉.png"
    mixed_root.mkdir()
    second.touch()
    assert image_batch_number(second) == "OGNWD9UB7QR3"
    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.prepare.gateway_config",
        lambda: ("https://example.test", "key"),
    )
    calls = []

    def fetch(code):
        calls.append(code)
        order, size = ("7AFYK3", "L") if code == "IRORKWQ8MKHZ" else ("ORDER8", "S")
        return {"batch_number": code, "records": [
            {"order_code": order, "order_item_code": f"{order}-1",
             "size": size, "color": "黑色"},
        ]}

    monkeypatch.setattr(
        "automatic_print.automation.api.s2b.metadata.prepare.fetch_s2b_batch_info", fetch,
    )
    result = prepare_s2b_metadata([image, second], SimpleNamespace())
    assert calls == ["IRORKWQ8MKHZ", "OGNWD9UB7QR3"]
    assert [record["matched_images"] for record in result] == [1, 1]

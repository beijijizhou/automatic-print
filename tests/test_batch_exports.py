from automatic_print.automation.transfer.exports import (
    production_image_export_records,
    ready_production_image_codes,
)


class Page:
    frames = [type("Frame", (), {"name": "fnsz-sale"})()]


def test_ready_codes_come_from_production_image_export(monkeypatch) -> None:
    monkeypatch.setattr(
        "automatic_print.automation.transfer.exports.call_module",
        lambda *_args, **_kwargs: [
            {"biz_no": "607250635009", "export_type": 3, "status": 2,
             "file_path": "https://files.hihumbird.com/a.zip"},
            {"biz_no": "607250635010", "export_type": 3, "status": 1},
            {"biz_no": "607250635011", "export_type": 2, "status": 2},
        ],
    )

    assert ready_production_image_codes(
        Page(),
        [
            {"code": "607250635009", "created": 1_700_000_000_000},
            {"code": "607250635010", "created": 1_700_000_000_001},
        ],
    ) == {"607250635009"}


def test_export_records_keep_newest_completed_file(monkeypatch) -> None:
    monkeypatch.setattr(
        "automatic_print.automation.transfer.exports.call_module",
        lambda *_args, **_kwargs: [
            {"biz_no": "607250635009", "export_type": 3, "status": 2,
             "finish_time": 10, "file_path": "https://files.hihumbird.com/old.zip"},
            {"biz_no": "607250635009", "export_type": 3, "status": 2,
             "finish_time": 20, "file_path": "https://files.hihumbird.com/new.zip"},
        ],
    )

    records = production_image_export_records(Page(), ["607250635009"])

    assert records["607250635009"]["file_path"].endswith("new.zip")

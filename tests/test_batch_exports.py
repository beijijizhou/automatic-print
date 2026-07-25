from automatic_print.automation.batch_exports import (
    ready_production_image_codes,
)


class Page:
    frames = [type("Frame", (), {"name": "fnsz-sale"})()]


def test_ready_codes_come_from_production_image_export(monkeypatch) -> None:
    monkeypatch.setattr(
        "automatic_print.automation.batch_exports.call_module",
        lambda *_args, **_kwargs: [
            {"biz_no": "607250635009", "export_type": 3, "status": 2},
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

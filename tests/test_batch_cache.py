from automatic_print.automation.batch_browser import BatchRecord
from automatic_print.batch_ui.batch_cache import (
    load_batch_cache,
    save_batch_cache,
)


class Settings:
    def __init__(self) -> None:
        self.data = {}

    def setValue(self, key, value) -> None:
        self.data[key] = value

    def value(self, key, default, _type):
        return self.data.get(key, default)


def test_batch_cache_survives_ui_navigation() -> None:
    settings = Settings()
    records = [
        BatchRecord(
            "607250203001",
            5,
            8,
            "多项多件",
            "2026-07-24 10:00:00",
            True,
        )
    ]

    saved_at = save_batch_cache(settings, "隆丰", records)
    loaded, loaded_at = load_batch_cache(settings, "隆丰")

    assert loaded == records
    assert loaded_at == saved_at
    assert load_batch_cache(settings, "Haloo") == ([], "")

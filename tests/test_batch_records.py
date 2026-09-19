from datetime import datetime

from automatic_print.automation.api.erp import records as batch_records


class _Rows:
    def all_inner_texts(self):
        return []


class _Frame:
    def locator(self, selector):
        assert selector == "tbody tr:visible"
        return _Rows()


def test_batch_time_comes_from_batch_created_field(monkeypatch) -> None:
    created = 1_700_000_000_000
    monkeypatch.setattr(
        batch_records, "production_batch_frame", lambda _page: _Frame()
    )

    records = batch_records.records_from_rows(
        object(),
        [{
            "code": "609180001001",
            "created": created,
            "finish_time": created + 99_000,
            "updated": created + 199_000,
        }],
    )

    expected = datetime.fromtimestamp(created / 1000).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    assert records[0].generated_at == expected
    assert records[0].created_at == expected

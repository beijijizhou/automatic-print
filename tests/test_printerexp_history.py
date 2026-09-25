import struct
from datetime import date

from automatic_print.automation.api.printerexp.history import read_print_history


def _qstring(value):
    raw = value.encode("utf-16le")
    return struct.pack("<I", len(raw)) + raw


def _stamp(year, month, day, hour, minute, second):
    weekday = (date(year, month, day).weekday() + 1) % 7
    return struct.pack("<8H", year, weekday, month, day, hour, minute, second, 0)


def _record(name, source, start, finish):
    body = (
        struct.pack("<I", 123) + _qstring(name) + _qstring("(null)") + _qstring(source)
        + _stamp(*start) + _stamp(*finish)
    )
    return struct.pack("<I", len(body)) + body


def test_reads_recent_records_from_printexp_native_history(tmp_path):
    data = tmp_path / "Data"
    data.mkdir()
    records = [
        _record("first.prn", r"C:\jobs\first.prn", (2026, 9, 24, 8, 0, 0), (2026, 9, 24, 8, 2, 0)),
        _record("second.prn", r"C:\jobs\second.prn", (2026, 9, 25, 9, 0, 0), (2026, 9, 25, 9, 1, 30)),
    ]
    (data / "recordTask.tf").write_bytes(
        b"T\x00S\x00" + struct.pack("<II", 25, len(records)) + b"".join(records)
    )

    result = read_print_history(tmp_path, limit=1, days=2, today=date(2026, 9, 25))

    assert result["total_records"] == 2
    assert result["records"] == [{
        "sequence": 2,
        "task_name": "second.prn",
        "source_path": r"C:\jobs\second.prn",
        "started_at": "2026-09-25T09:00:00",
        "finished_at": "2026-09-25T09:01:30",
        "duration_seconds": 90,
    }]

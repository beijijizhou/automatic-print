import struct
from datetime import date

from automatic_print.automation.api.printerexp.history import read_print_history


def _qstring(value):
    raw = value.encode("utf-16le")
    return struct.pack("<I", len(raw)) + raw


def _task_record(name, source):
    body = struct.pack("<I", 123) + _qstring(name) + _qstring("(null)") + _qstring(source)
    return struct.pack("<I", len(body)) + body


def _write_log(root, day, lines):
    folder = root / "Log" / "main"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"Log[{day}].txt").write_text("\n".join(lines), encoding="utf-16")


def test_reads_completed_prn_jobs_from_printexp_logs(tmp_path):
    data = tmp_path / "Data"
    data.mkdir()
    task = _task_record("second.prn", r"C:\jobs\second.prn")
    (data / "recordTask.tf").write_bytes(
        b"T\x00S\x00" + struct.pack("<II", 25, 1) + task
    )
    _write_log(tmp_path, "2026_09_24", [
        "[08:00:00.000][软件][调试] 启动任务：first.prn",
        "[08:02:00.000][软件][调试] 作业打印完成.作业ID：1",
    ])
    _write_log(tmp_path, "2026_09_25", [
        "[09:00:00.000][软件][调试] 启动任务：second.prn",
        "[09:01:30.000][软件][调试] 作业打印完成.作业ID：2",
    ])

    result = read_print_history(tmp_path, limit=1, days=2, today=date(2026, 9, 25))

    assert result["total_records"] == 2
    assert result["diagnostics"]["log_files_checked"] == [
        "Log[2026_09_24].txt", "Log[2026_09_25].txt",
    ]
    assert result["diagnostics"]["available_log_files"] == [
        "Log[2026_09_25].txt", "Log[2026_09_24].txt",
    ]
    assert result["diagnostics"]["start_events"] == 2
    assert result["diagnostics"]["completion_events"] == 2
    assert result["records"] == [{
        "sequence": 2,
        "task_name": "second.prn",
        "source_path": r"C:\jobs\second.prn",
        "started_at": "2026-09-25T09:00:00",
        "finished_at": "2026-09-25T09:01:30",
        "duration_seconds": 90,
    }]


def test_ignores_maintenance_and_unfinished_jobs(tmp_path):
    _write_log(tmp_path, "2026_09_25", [
        "[09:00:00.000][软件][调试] 启动任务：I3200_3H4C",
        "[09:00:30.000][软件][调试] 作业打印完成.作业ID：1",
        "[10:00:00.000][软件][调试] 启动任务：still-printing.prn",
    ])

    result = read_print_history(tmp_path, days=2, today=date(2026, 9, 25))

    assert result["records"] == []
    assert result["total_records"] == 0


def test_falls_back_to_latest_available_logs_without_claiming_recent_dates(tmp_path):
    _write_log(tmp_path, "2026_03_24", [
        "[09:00:00.000][软件][调试] 启动任务：old.prn",
        "[09:01:00.000][软件][调试] 作业打印完成.作业ID：1",
    ])

    result = read_print_history(tmp_path, days=2, today=date(2026, 9, 25))

    assert result["total_records"] == 1
    assert result["records"][0]["started_at"] == "2026-03-24T09:00:00"
    assert result["diagnostics"]["range_fallback"] is True
    assert result["diagnostics"]["log_files_checked"] == ["Log[2026_03_24].txt"]

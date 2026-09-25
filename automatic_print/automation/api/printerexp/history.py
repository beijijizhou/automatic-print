"""Read recent records from PrintExp's own history file."""

from datetime import date, datetime, timedelta
from pathlib import Path, PureWindowsPath
import struct

from .discovery import find_installation


MAGIC = b"T\x00S\x00"


def read_print_history(installation=None, *, limit=500, days=2, today=None):
    root = Path(installation) if installation else find_installation()
    if root is None:
        raise RuntimeError("未找到 PrintExp 安装目录。")
    path = root / "Data" / "recordTask.tf"
    raw = path.read_bytes()
    if len(raw) < 12 or raw[:4] != MAGIC:
        raise RuntimeError("PrintExp 历史文件格式无法识别。")
    declared = struct.unpack_from("<I", raw, 8)[0]
    records, offset = [], 12
    range_days = max(1, min(int(days), 31))
    last_day = today or date.today()
    first_day = last_day - timedelta(days=range_days - 1)
    for index in range(declared):
        if offset + 4 > len(raw):
            raise RuntimeError("PrintExp 历史文件记录不完整。")
        size = struct.unpack_from("<I", raw, offset)[0]
        start, end = offset + 4, offset + 4 + size
        if size < 8 or end > len(raw):
            raise RuntimeError("PrintExp 历史文件记录长度无效。")
        block = raw[start:end]
        name, cursor = _string(block, 4)
        _unused, cursor = _string(block, cursor)
        source, cursor = _string(block, cursor)
        started, finished = _times(block, cursor)
        if name and started is not None and first_day <= started.date() <= last_day:
            records.append({
                "sequence": index + 1,
                "task_name": PureWindowsPath(name).name,
                "source_path": source,
                "started_at": started.isoformat(timespec="seconds"),
                "finished_at": finished.isoformat(timespec="seconds"),
                "duration_seconds": max(0, int((finished - started).total_seconds())),
            })
        offset = end
    if offset != len(raw):
        raise RuntimeError("PrintExp 历史文件尾部存在未知数据。")
    records.sort(key=lambda item: item["started_at"], reverse=True)
    count = max(1, min(int(limit), 500))
    return {
        "records": records[:count],
        "total_records": len(records),
        "range_days": range_days,
    }


def _string(block, offset):
    if offset + 4 > len(block):
        raise RuntimeError("PrintExp 历史字符串不完整。")
    size = struct.unpack_from("<I", block, offset)[0]
    start, end = offset + 4, offset + 4 + size
    if size > len(block) or size % 2 or end > len(block):
        raise RuntimeError("PrintExp 历史字符串长度无效。")
    return block[start:end].decode("utf-16le", errors="replace").rstrip("\x00"), end


def _times(block, start):
    for offset in range(start, len(block) - 31):
        first = _datetime(block, offset)
        second = _datetime(block, offset + 16)
        if first is not None and second is not None and second >= first:
            return first, second
    return None, None


def _datetime(block, offset):
    year, weekday, month, day, hour, minute, second, milliseconds = struct.unpack_from(
        "<8H", block, offset,
    )
    try:
        value = datetime(year, month, day, hour, minute, second, milliseconds * 1000)
    except ValueError:
        return None
    expected_weekday = (value.weekday() + 1) % 7
    if not 2000 <= year <= 2100 or weekday != expected_weekday:
        return None
    return value

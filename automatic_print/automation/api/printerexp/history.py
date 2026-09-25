"""Read completed PRN jobs from PrintExp's own daily logs."""

from datetime import date, datetime, timedelta
from pathlib import Path, PureWindowsPath
import re
import struct

from .discovery import find_installation


MAGIC = b"T\x00S\x00"
START_RE = re.compile(
    r"^\[(\d{2}:\d{2}:\d{2}\.\d{3})\].*?启动任务：(.*?)\s*$"
)
TIME_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2}\.\d{3})\]")
COMPLETED_MARKER = "作业打印完成."


def read_print_history(installation=None, *, limit=500, days=2, today=None):
    root = Path(installation) if installation else find_installation()
    if root is None:
        raise RuntimeError("未找到 PrintExp 安装目录。")
    range_days = max(1, min(int(days), 31))
    last_day = today or date.today()
    first_day = last_day - timedelta(days=range_days - 1)
    sources = _task_sources(root / "Data" / "recordTask.tf")
    records = _completed_jobs(root, first_day, last_day, sources)
    count = max(1, min(int(limit), 500))
    return {
        "records": list(reversed(records))[:count],
        "total_records": len(records),
        "range_days": range_days,
    }


def _completed_jobs(root, first_day, last_day, sources):
    records, active = [], None
    day = first_day
    while day <= last_day:
        path = root / "Log" / "main" / f"Log[{day:%Y_%m_%d}].txt"
        if path.is_file():
            active = _read_log(path, day, active, records, sources)
        day += timedelta(days=1)
    for sequence, record in enumerate(records, 1):
        record["sequence"] = sequence
    return records


def _read_log(path, day, active, records, sources):
    with path.open("r", encoding="utf-16", errors="replace") as stream:
        for line in stream:
            started = START_RE.match(line)
            if started:
                name = started.group(2).strip()
                active = (name, _timestamp(day, started.group(1)))
                continue
            if COMPLETED_MARKER not in line or active is None:
                continue
            finished = TIME_RE.match(line)
            name, started_at = active
            active = None
            if finished is None or not name.lower().endswith(".prn"):
                continue
            finished_at = _timestamp(day, finished.group(1))
            if finished_at < started_at:
                continue
            records.append({
                "task_name": PureWindowsPath(name).name,
                "source_path": sources.get(name.casefold(), ""),
                "started_at": started_at.isoformat(timespec="seconds"),
                "finished_at": finished_at.isoformat(timespec="seconds"),
                "duration_seconds": max(0, int((finished_at - started_at).total_seconds())),
            })
    return active


def _timestamp(day, value):
    parsed = datetime.strptime(value, "%H:%M:%S.%f").time()
    return datetime.combine(day, parsed)


def _task_sources(path):
    try:
        raw = path.read_bytes()
        if len(raw) < 12 or raw[:4] != MAGIC:
            return {}
        declared = struct.unpack_from("<I", raw, 8)[0]
        sources, offset = {}, 12
        for _index in range(declared):
            size = struct.unpack_from("<I", raw, offset)[0]
            block = raw[offset + 4:offset + 4 + size]
            name, cursor = _string(block, 4)
            _unused, cursor = _string(block, cursor)
            source, _cursor = _string(block, cursor)
            if name and source:
                sources.setdefault(name.casefold(), source)
            offset += 4 + size
        return sources
    except (OSError, UnicodeError, struct.error, ValueError):
        return {}


def _string(block, offset):
    size = struct.unpack_from("<I", block, offset)[0]
    start, end = offset + 4, offset + 4 + size
    if size % 2 or end > len(block):
        raise ValueError("invalid PrintExp string")
    return block[start:end].decode("utf-16le", errors="replace").rstrip("\x00"), end

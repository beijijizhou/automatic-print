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
LOG_NAME_RE = re.compile(r"^Log\[(\d{4})_(\d{2})_(\d{2})\]\.txt$", re.IGNORECASE)
COMPLETED_MARKER = "作业打印完成."


def read_print_history(installation=None, *, limit=500, days=2, today=None):
    root = Path(installation) if installation else find_installation()
    if root is None:
        raise RuntimeError("未找到 PrintExp 安装目录。")
    range_days = max(1, min(int(days), 31))
    last_day = today or date.today()
    first_day = last_day - timedelta(days=range_days - 1)
    task_records = _task_records(root / "Data" / "recordTask.tf")
    sources = {
        item["task_name"].casefold(): item["source_path"]
        for item in task_records if item.get("task_name") and item.get("source_path")
    }
    records, diagnostics = _completed_jobs(root, first_day, last_day, sources)
    task_fallback = not records and diagnostics.get("range_fallback") and task_records
    diagnostics["task_file_fallback"] = bool(task_fallback)
    if task_fallback:
        records = task_records
    count = max(1, min(int(limit), 500))
    return {
        "records": records[:count] if task_fallback else list(reversed(records))[:count],
        "total_records": len(records),
        "range_days": range_days,
        "diagnostics": diagnostics,
    }


def _completed_jobs(root, first_day, last_day, sources):
    records, active = [], None
    log_directory = root / "Log" / "main"
    diagnostics = {
        "installation": str(root),
        "log_directory_exists": log_directory.is_dir(),
        "available_log_files": _recent_log_names(log_directory),
        "log_files_checked": [],
        "start_events": 0,
        "completion_events": 0,
        "range_fallback": False,
    }
    candidates = _dated_logs(log_directory, first_day, last_day)
    if not candidates:
        candidates = _latest_dated_logs(log_directory, limit=2)
        diagnostics["range_fallback"] = bool(candidates)
    for day, path in candidates:
        diagnostics["log_files_checked"].append(path.name)
        active, starts, completions = _read_log(
            path, day, active, records, sources,
        )
        diagnostics["start_events"] += starts
        diagnostics["completion_events"] += completions
    for sequence, record in enumerate(records, 1):
        record["sequence"] = sequence
    return records, diagnostics


def _recent_log_names(directory, limit=10):
    try:
        files = [path for path in directory.iterdir() if path.is_file()]
        files.sort(key=lambda path: (path.stat().st_mtime, path.name), reverse=True)
        return [path.name for path in files[:limit]]
    except OSError:
        return []


def _dated_logs(directory, first_day, last_day):
    paths = []
    day = first_day
    while day <= last_day:
        path = directory / f"Log[{day:%Y_%m_%d}].txt"
        if path.is_file():
            paths.append((day, path))
        day += timedelta(days=1)
    return paths


def _latest_dated_logs(directory, limit=2):
    try:
        candidates = []
        for path in directory.iterdir():
            matched = LOG_NAME_RE.match(path.name)
            if not path.is_file() or matched is None:
                continue
            try:
                day = date(*(int(value) for value in matched.groups()))
            except ValueError:
                continue
            candidates.append((day, path))
        candidates.sort(key=lambda item: item[0])
        return candidates[-max(1, int(limit)):]
    except OSError:
        return []


def _read_log(path, day, active, records, sources):
    starts = completions = 0
    with path.open("r", encoding="utf-16", errors="replace") as stream:
        for line in stream:
            started = START_RE.match(line)
            if started:
                starts += 1
                name = started.group(2).strip()
                active = (name, _timestamp(day, started.group(1)))
                continue
            if COMPLETED_MARKER not in line or active is None:
                continue
            completions += 1
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
    return active, starts, completions


def _timestamp(day, value):
    parsed = datetime.strptime(value, "%H:%M:%S.%f").time()
    return datetime.combine(day, parsed)


def _task_records(path):
    try:
        raw = path.read_bytes()
        if len(raw) < 12 or raw[:4] != MAGIC:
            return []
        declared = struct.unpack_from("<I", raw, 8)[0]
        records, offset = [], 12
        for index in range(declared):
            size = struct.unpack_from("<I", raw, offset)[0]
            block = raw[offset + 4:offset + 4 + size]
            name, cursor = _string(block, 4)
            _unused, cursor = _string(block, cursor)
            source, _cursor = _string(block, cursor)
            if name:
                records.append({
                    "sequence": index + 1,
                    "task_name": PureWindowsPath(name).name,
                    "source_path": source,
                    "started_at": "",
                    "finished_at": "",
                    "duration_seconds": 0,
                    "time_unavailable": True,
                })
            offset += 4 + size
        return records
    except (OSError, UnicodeError, struct.error, ValueError):
        return []


def _string(block, offset):
    size = struct.unpack_from("<I", block, offset)[0]
    start, end = offset + 4, offset + 4 + size
    if size % 2 or end > len(block):
        raise ValueError("invalid PrintExp string")
    return block[start:end].decode("utf-16le", errors="replace").rstrip("\x00"), end

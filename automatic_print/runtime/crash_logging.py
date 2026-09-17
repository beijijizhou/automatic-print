from __future__ import annotations

import faulthandler
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable


def log_folder() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if root:
        folder = Path(root) / "AutomaticPrint" / "logs"
    else:
        folder = Path.home() / ".automatic-print" / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def latest_log_path() -> Path:
    return log_folder() / "latest-startup.log"


def _write_exception(kind, value, traceback_object) -> None:
    path = latest_log_path()
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            f"\n[{datetime.now().isoformat(timespec='seconds')}] "
            "未处理异常\n"
        )
        traceback.print_exception(
            kind, value, traceback_object, file=stream
        )
    sys.__excepthook__(kind, value, traceback_object)


def run_with_crash_logging(run_app: Callable[[], int]) -> int:
    path = latest_log_path()
    fault_stream = path.open("a", encoding="utf-8")
    faulthandler.enable(file=fault_stream, all_threads=True)
    sys.excepthook = _write_exception
    fault_stream.write(
        f"\n[{datetime.now().isoformat(timespec='seconds')}] 正在启动\n"
    )
    fault_stream.flush()
    try:
        result = run_app()
        fault_stream.write(
            f"[{datetime.now().isoformat(timespec='seconds')}] "
            f"正常结束，返回值 {result}\n"
        )
        return result
    except BaseException:
        kind, value, traceback_object = sys.exc_info()
        _write_exception(kind, value, traceback_object)
        return 1
    finally:
        faulthandler.disable()
        fault_stream.close()

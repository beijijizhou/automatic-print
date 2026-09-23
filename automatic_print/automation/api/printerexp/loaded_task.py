"""Persist the last PRN accepted by PrintExp's open-file dialog."""

import json
import os
import time
from pathlib import Path


def loaded_task_file():
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".automatic-print")
    return root / "AutomaticPrint" / "printexp-loaded-task.json"


def record_loaded_task(path, *, verified=False, now=None, target=None):
    task = Path(path).resolve()
    payload = {
        "task_file": task.name,
        "task_path": str(task),
        "loaded_at": float(time.time() if now is None else now),
        "task_name_verified": bool(verified),
        "verification": "visible_task_name" if verified else "load_dialog_closed_ready",
    }
    destination = Path(target) if target is not None else loaded_task_file()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(destination)
    return payload


def read_loaded_task(*, now=None, max_age=8 * 60 * 60, target=None):
    source = Path(target) if target is not None else loaded_task_file()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        task_path = Path(str(payload.get("task_path") or ""))
        loaded_at = float(payload.get("loaded_at"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    current = float(time.time() if now is None else now)
    if (
        not payload.get("task_file")
        or task_path.suffix.casefold() != ".prn"
        or not task_path.is_file()
        or current < loaded_at
        or current - loaded_at > float(max_age)
    ):
        return None
    return payload

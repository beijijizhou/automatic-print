"""Project PrintExp snapshots and native state into fleet status."""

from collections import deque
from datetime import datetime, timezone
from time import monotonic

from ..state_machine import IDLE, PRINTING, UNKNOWN, project_printer_state


class StatusProjector:
    def __init__(self):
        self.task_id = ""
        self.started_at = None
        self.samples = deque(maxlen=30)

    def project(
        self, snapshot, online, *, printer_state=None, loaded_task=None,
        clock=None, timestamp=None,
    ):
        now = monotonic() if clock is None else float(clock)
        moment = timestamp or datetime.now(timezone.utc).isoformat()
        if not online:
            self.samples.clear()
            return _base("stopped", "PrintExp未运行", False)
        if snapshot is None:
            if loaded_task:
                return _loaded_receipt(loaded_task)
            return _base("idle", "PrintExp在线，等待任务", True, "idle")
        printer_state = printer_state or PRINTING
        if (
            loaded_task
            and float(loaded_task.get("loaded_at") or 0) >= snapshot.modified_at
        ):
            return _loaded_receipt(loaded_task)
        if snapshot.task_id != self.task_id:
            self.task_id = snapshot.task_id
            self.started_at = moment if snapshot.progress < 100 else None
            self.samples.clear()
        if snapshot.progress >= 100:
            self.samples.clear()
            self.started_at = None
            state, phase, remaining = "idle", "PrintExp在线待机", None
            printer_state = IDLE
        else:
            self._sample(now, snapshot.progress)
            state, phase = project_printer_state(printer_state)
            remaining = self._remaining(snapshot.progress) if printer_state == PRINTING else None
        return {
            **_base(state, phase, True),
            "progress_percent": round(snapshot.progress),
            "batch_id": snapshot.task_id or snapshot.task_file or None,
            "batch_name": snapshot.task_file or snapshot.task_folder or None,
            "batch_info": {
                "provider": "PrintExp", "task_file": snapshot.task_file or None,
                "task_folder": snapshot.task_folder or None,
                "printer_state": printer_state or UNKNOWN,
                "task_name_verified": bool(snapshot.task_file),
                "task_source": "PrintInfo.ini",
            },
            "remaining_seconds": remaining,
            "estimate_scope": "batch" if remaining is not None else None,
            "started_at": self.started_at,
        }

    def _sample(self, now, progress):
        if not self.samples or progress != self.samples[-1][1]:
            if self.samples and progress < self.samples[-1][1]:
                self.samples.clear()
            self.samples.append((now, progress))

    def _remaining(self, progress):
        if len(self.samples) < 2:
            return None
        start_time, start_progress = self.samples[0]
        end_time, end_progress = self.samples[-1]
        gained = end_progress - start_progress
        if gained < 0.1 or end_time <= start_time:
            return None
        return round((end_time - start_time) / gained * (100 - progress))


def _base(state, phase, source_online, printer_state=None):
    return {
        "department": "DTF", "state": state, "phase": phase,
        "source_online": source_online, "progress_percent": None,
        "batch_id": None, "batch_name": None,
        "batch_info": {"provider": "PrintExp", "printer_state": printer_state},
        "remaining_seconds": None, "estimate_scope": None,
        "started_at": None, "error_message": None,
    }


def _loaded_receipt(receipt):
    verified = receipt.get("task_name_verified") is True
    task_file = str(receipt.get("task_file") or "").strip()
    phase = "PrintExp待打印" if verified else "PrintExp待打印（文件名待状态文件复核）"
    return {
        **_base("idle", phase, True, "ready"),
        "progress_percent": 0,
        "batch_id": task_file or None,
        "batch_name": task_file or None,
        "batch_info": {
            "provider": "PrintExp", "task_file": task_file or None,
            "task_folder": None, "printer_state": "ready",
            "task_name_verified": verified, "task_source": "load_receipt",
            "verification": receipt.get("verification"),
        },
    }

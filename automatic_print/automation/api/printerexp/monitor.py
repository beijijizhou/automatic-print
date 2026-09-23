"""Continuously project PrintExp state to the shared Supabase endpoint."""

import logging
import os
from collections import deque
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Event
from time import monotonic

from ..machine_status import claim_control, report_machine
from ..machine_commands import CommandDispatcher
from .discovery import find_installation, process_running, running_installations
from .state import read_snapshot


class StatusProjector:
    def __init__(self):
        self.task_id = ""
        self.started_at = None
        self.samples = deque(maxlen=30)

    def project(self, snapshot, online, *, clock=None, timestamp=None):
        now = monotonic() if clock is None else float(clock)
        moment = timestamp or datetime.now(timezone.utc).isoformat()
        if not online:
            self.samples.clear()
            return _base("stopped", "PrintExp未运行", False)
        if snapshot is None:
            return _base("idle", "PrintExp在线，等待任务", True)
        if snapshot.task_id != self.task_id:
            self.task_id = snapshot.task_id
            self.started_at = moment if snapshot.progress < 100 else None
            self.samples.clear()
        if snapshot.progress >= 100:
            self.samples.clear()
            self.started_at = None
            state, phase, remaining = "idle", "PrintExp在线待机", None
        else:
            self._sample(now, snapshot.progress)
            state, phase = "running", "PrintExp打印中"
            remaining = self._remaining(snapshot.progress)
        return {
            **_base(state, phase, True),
            "progress_percent": round(snapshot.progress),
            "batch_id": snapshot.task_id or snapshot.task_file or None,
            "batch_name": snapshot.task_file or snapshot.task_folder or None,
            "batch_info": {
                "provider": "PrintExp",
                "task_file": snapshot.task_file or None,
                "task_folder": snapshot.task_folder or None,
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


class PrintExpMonitor:
    def __init__(
        self,
        *,
        poll_seconds=2,
        heartbeat_seconds=60,
        send=report_machine,
        command_dispatcher=None,
        control_dispatcher=None,
    ):
        self.poll_seconds = float(poll_seconds)
        self.heartbeat_seconds = float(heartbeat_seconds)
        self.send = send
        self.stop_event = Event()
        self.projector = StatusProjector()
        self.installation = None
        self.last_signature = None
        self.last_attempt = 0.0
        self.logger = _logger()
        self.command_dispatcher = command_dispatcher or CommandDispatcher()
        self.control_dispatcher = control_dispatcher or CommandDispatcher(
            poll_seconds=0.5, claim=claim_control,
        )

    def run(self):
        next_status = 0.0
        while not self.stop_event.is_set():
            try:
                self.control_dispatcher.tick()
            except Exception as error:
                self.logger.warning("Unable to poll realtime printer controls: %s", error)
            try:
                self.command_dispatcher.tick()
            except Exception as error:
                self.logger.warning("Unable to poll remote commands: %s", error)
            now = monotonic()
            if now >= next_status:
                self.run_once()
                next_status = now + self.poll_seconds
            self.stop_event.wait(0.25)

    def run_once(self):
        active_installations = running_installations()
        if active_installations:
            self.installation = max(active_installations, key=_status_modified_at)
        elif self.installation is None:
            self.installation = find_installation()
        online = process_running()
        snapshot = None
        if self.installation is not None:
            try:
                snapshot = read_snapshot(self.installation)
            except OSError as error:
                self.logger.warning("Unable to read PrintExp status: %s", error)
        status = self.projector.project(snapshot, online)
        signature = _signature(status)
        now = monotonic()
        changed = signature != self.last_signature
        if not changed and now - self.last_attempt < self.heartbeat_seconds:
            return status
        self.last_signature, self.last_attempt = signature, now
        try:
            self.send(status)
        except Exception as error:
            self.logger.warning("Unable to publish PrintExp status: %s", error)
        return status

    def stop(self):
        self.stop_event.set()


def _base(state, phase, source_online):
    return {
        "department": "DTF", "state": state, "phase": phase,
        "source_online": source_online, "progress_percent": None,
        "batch_id": None, "batch_name": None, "batch_info": {"provider": "PrintExp"},
        "remaining_seconds": None, "estimate_scope": None,
        "started_at": None, "error_message": None,
    }


def _signature(status):
    return tuple(str(status.get(name)) for name in (
        "state", "phase", "source_online", "progress_percent", "batch_id",
        "batch_name", "remaining_seconds", "error_message",
    ))


def _status_modified_at(installation):
    try:
        return (Path(installation) / "Data" / "PrintInfo.ini").stat().st_mtime
    except OSError:
        return 0


def _logger():
    logger = logging.getLogger("automatic-print.printerexp-monitor")
    if logger.handlers:
        return logger
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".automatic-print")
    try:
        target = root / "AutomaticPrint" / "printerexp-monitor.log"
        target.parent.mkdir(parents=True, exist_ok=True)
        logger.addHandler(RotatingFileHandler(target, maxBytes=1_000_000, backupCount=2))
    except OSError:
        logger.addHandler(logging.NullHandler())
    logger.setLevel(logging.INFO)
    return logger

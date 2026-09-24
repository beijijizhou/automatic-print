"""Continuously project PrintExp state to the shared Supabase endpoint."""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Event
from time import monotonic

from ..machine_status import claim_control, report_machine
from ..machine_commands import CommandDispatcher
from ....runtime.monitoring.control import AutomationWakeListener, automation_enabled
from .controls import NativePrintExpControls
from .discovery import find_installation, process_running, running_installations
from .loaded_task import read_loaded_task
from .state import read_snapshot
from .status.projection import StatusProjector


class PrintExpMonitor:
    def __init__(
        self,
        *,
        poll_seconds=2,
        heartbeat_seconds=300,
        send=report_machine,
        command_dispatcher=None,
        control_dispatcher=None,
        automation_allowed=automation_enabled,
        wake_listener=None,
    ):
        self.poll_seconds = float(poll_seconds)
        self.heartbeat_seconds = float(heartbeat_seconds)
        self.send = send
        self.automation_allowed = automation_allowed
        self.wake_listener = wake_listener or AutomationWakeListener()
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
        self.wake_listener.start()
        next_status = 0.0
        try:
            while not self.stop_event.is_set():
                if not self.automation_allowed():
                    self.last_signature = None
                    self.stop_event.wait(0.25)
                    continue
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
        finally:
            self.wake_listener.stop()

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
        loaded_task = read_loaded_task() if online else None
        printer_state = _printer_state(snapshot, online, self.logger, loaded_task)
        status = self.projector.project(
            snapshot, online, printer_state=printer_state, loaded_task=loaded_task,
        )
        if not self.automation_allowed():
            self.last_signature = None
            return status
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


def _signature(status):
    return tuple(str(status.get(name)) for name in (
        "state", "phase", "source_online", "progress_percent", "batch_id",
        "batch_name", "batch_info", "error_message",
    ))


def _printer_state(snapshot, online, logger, loaded_task=None):
    if not online:
        return None
    if snapshot is not None and snapshot.progress >= 100:
        return "idle"
    loaded = bool(loaded_task or (snapshot and snapshot.progress == 0 and (
        snapshot.task_file or snapshot.task_folder
    )))
    try:
        return NativePrintExpControls().operation_state(task_loaded=loaded)
    except Exception as error:
        logger.warning("Unable to inspect PrintExp controls: %s", error)
        return "unknown"


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

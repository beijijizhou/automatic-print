"""Continuously project PrintExp state to the shared Supabase endpoint."""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Event
from time import monotonic

from ..machine_status import claim_control, report_machine
from ..machine_status.identity import machine_id
from ..machine_commands import CommandDispatcher
from ..machine_commands.lifecycle import recover_pending_receipts, reconcile_printer_status
from ....runtime.monitoring.cloud_wake import HybridWakeListener
from .control import NativePrintExpControls
from .discovery import find_installation, process_running, running_installations
from .status.loaded_task import read_loaded_task
from .state import read_snapshot
from .state_machine import IDLE, UNKNOWN
from .status.projection import StatusProjector


class PrintExpMonitor:
    def __init__(
        self,
        *,
        poll_seconds=2,
        send=report_machine,
        command_dispatcher=None,
        control_dispatcher=None,
        automation_allowed=None,
        wake_listener=None,
    ):
        self.poll_seconds = float(poll_seconds)
        self.send = send
        self.automation_allowed = automation_allowed
        self.dispatch_event = Event()
        self.wake_listener = wake_listener or HybridWakeListener(
            dispatch=self.request_dispatch, target_machine_id=machine_id(),
        )
        self.stop_event = Event()
        self.projector = StatusProjector()
        self.installation = None
        self.last_signature = None
        self.logger = _logger()
        self.command_dispatcher = command_dispatcher or CommandDispatcher()
        self.control_dispatcher = control_dispatcher or CommandDispatcher(
            poll_seconds=0.5, claim=claim_control,
        )

    def run(self):
        self.wake_listener.start()
        self._claim_startup_command()
        next_status = 0.0
        try:
            while not self.stop_event.is_set():
                if self.dispatch_event.is_set():
                    self.dispatch_event.clear()
                    self._tick_dispatchers(force=True)
                now = monotonic()
                if now >= next_status:
                    self.run_once()
                    next_status = now + self.poll_seconds
                self.stop_event.wait(0.25)
        finally:
            self.wake_listener.stop()

    def request_dispatch(self, _payload=None):
        self.dispatch_event.set()

    def _claim_startup_command(self):
        """One startup read recovers a fleet update missed while powered off."""
        try:
            recover_pending_receipts()
            self.command_dispatcher.next_poll = 0.0
            self.command_dispatcher.tick()
        except Exception as error:
            self.logger.warning("Unable to recover startup command: %s", error)

    def _tick_dispatchers(self, *, force=False):
        busy = False
        for label, dispatcher in (
            ("realtime printer controls", self.control_dispatcher),
            ("remote commands", self.command_dispatcher),
        ):
            if force:
                dispatcher.next_poll = 0.0
            try:
                dispatcher.tick()
            except Exception as error:
                self.logger.warning("Unable to poll %s: %s", label, error)
            busy = busy or getattr(dispatcher, "process", None) is not None
        if force and busy:
            self.dispatch_event.set()

    def run_once(self):
        status = self.collect_status()
        signature = _signature(status)
        changed = signature != self.last_signature
        if not changed:
            return status
        try:
            reconcile_printer_status(status)
            recover_pending_receipts()
        except Exception as error:
            self.logger.warning("Unable to reconcile local command journal: %s", error)
        try:
            self.send(status)
        except Exception as error:
            self.logger.warning("Unable to publish PrintExp status: %s", error)
        else:
            self.last_signature = signature
        return status

    def collect_status(self):
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
        return IDLE
    loaded = bool(loaded_task or (snapshot and snapshot.progress == 0 and (
        snapshot.task_file or snapshot.task_folder
    )))
    try:
        return NativePrintExpControls().operation_state(task_loaded=loaded)
    except Exception as error:
        logger.warning("Unable to inspect PrintExp controls: %s", error)
        return UNKNOWN


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

"""Idempotent local execution and deferred cloud receipt handling."""

from time import monotonic

from .journal import ExecutionJournal, TERMINAL_STAGES
from ..machine_status.commands import update_command


class CommandProgress:
    def __init__(self, command_id, send=update_command, interval=2):
        self.command_id = command_id
        self.send = send
        self.interval = float(interval)
        self.last_sent = 0.0
        self.last_message = ""

    def __call__(self, message, *, force=False):
        message = str(message).strip()[:300]
        now = monotonic()
        if not force and (message == self.last_message or now - self.last_sent < self.interval):
            return
        self.send(self.command_id, "running", phase=message)
        self.last_sent, self.last_message = now, message


class CommandLifecycle:
    def __init__(self, command_id, action, payload, *, journal=None, publish=update_command):
        self.command_id = str(command_id)
        self.action = str(action)
        self.payload = dict(payload or {})
        self.journal = journal or ExecutionJournal()
        self.publish = publish

    def begin(self):
        existing = self.journal.claim(self.command_id, self.action, self.payload)
        if existing is None:
            return None
        if existing.get("stage") in TERMINAL_STAGES:
            self._publish(existing)
            return 0 if existing.get("cloud_status") == "succeeded" else 1
        message = "发现同一指令的本地未完成记录；为防止重复生产，已停止自动重试。"
        record = self.journal.failure(
            self.command_id, self.action, self.payload, "等待人工核查", message,
        )
        self._publish(record)
        return 1

    def succeed(self, phase, result):
        record = self.journal.success(
            self.command_id, self.action, self.payload, phase, result,
        )
        self._publish(record)

    def fail(self, phase, error, result=None):
        record = self.journal.failure(
            self.command_id, self.action, self.payload, phase, error, result,
        )
        self._publish(record)

    def _publish(self, record):
        if not record or record.get("cloud_status") not in {"succeeded", "failed"}:
            return False
        try:
            self.publish(
                self.command_id, record["cloud_status"], phase=record.get("phase") or "",
                progress_percent=100 if record["cloud_status"] == "succeeded" else None,
                result=record.get("result") or {},
                error_message=record.get("error_message") or None,
            )
        except Exception:
            return False
        self.journal.mark_reported(self.command_id)
        return True


def recover_pending_receipts(*, journal=None, publish=update_command):
    journal = journal or ExecutionJournal()
    recovered = 0
    for record in journal.pending_receipts():
        lifecycle = CommandLifecycle(
            record["command_id"], record["action"], record["payload"],
            journal=journal, publish=publish,
        )
        recovered += bool(lifecycle._publish(record))
    return recovered


def reconcile_printer_status(status, *, journal=None):
    return (journal or ExecutionJournal()).reconcile(status)

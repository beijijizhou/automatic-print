"""Workers and display helpers for fleet source version management."""

from threading import Lock, Thread

from PySide6.QtCore import QObject, Signal

from ..automation.api.machine_status.commands import submit_source_update
from ..updates.source import SourceUpdater

ACTIVE = {"queued", "claimed", "running"}


class FleetUpdateSubmitter(QObject):
    completed = Signal(object)

    def __init__(self, parent=None, submit=submit_source_update):
        super().__init__(parent)
        self.submit = submit
        self.lock = Lock()

    def start(self, machines, revision, version):
        if not self.lock.acquire(blocking=False):
            return False
        Thread(target=self._run, args=(machines, revision, version), daemon=True,
               name="fleet-source-version").start()
        return True

    def _run(self, machines, revision, version):
        sent, failures = [], []
        try:
            for machine in machines:
                name = str(machine.get("machine_name") or "未知机器")
                try:
                    command = self.submit(machine["machine_id"], revision, version)
                    sent.append({"machine": name, "command": command})
                except Exception as error:
                    failures.append({"machine": name, "error": str(error)})
        finally:
            self.lock.release()
            self.completed.emit({"sent": sent, "failures": failures})


class FleetVersionLoader(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None, updater_factory=SourceUpdater):
        super().__init__(parent)
        self.updater_factory = updater_factory
        self.lock = Lock()

    def start(self):
        if not self.lock.acquire(blocking=False):
            return False
        Thread(target=self._run, daemon=True, name="fleet-version-catalog").start()
        return True

    def _run(self):
        try:
            versions = self.updater_factory().available_versions()
        except Exception as error:
            self.failed.emit(str(error))
        else:
            self.completed.emit(versions)
        finally:
            self.lock.release()


def version_key(value):
    try:
        return tuple(int(item) for item in str(value).split("."))
    except ValueError:
        return (0, 0, 0)


def update_state(machine, commands, target_version):
    if machine.get("identity_conflict"):
        return "机器号冲突"
    current = str(machine.get("app_version") or "")
    if current == str(target_version):
        return "已是目标版本"
    machine_id = str(machine.get("machine_id") or "")
    matches = [item for item in commands if item.get("action") == "source_update"
               and str(item.get("target_machine_id") or "") == machine_id
               and str((item.get("payload") or {}).get("target_version")
                       or target_version) == str(target_version)]
    if not matches:
        return "待回滚" if version_key(current) > version_key(target_version) else "待更新"
    command = max(matches, key=lambda item: str(item.get("created_at") or ""))
    status = str(command.get("status") or "")
    rollback = version_key(current) > version_key(target_version)
    label = {
        "queued": "等待领取", "claimed": "已领取",
        "running": "回滚中" if rollback else "更新中",
        "succeeded": "源码已切换，等待重启回报",
        "failed": "回滚失败" if rollback else "更新失败",
        "cancelled": "已被新指令替代", "expired": "未领取，已过期",
    }.get(status, status or "状态未知")
    detail = command.get("phase") or command.get("error_message")
    return f"{label} · {detail}" if detail else label

"""One-click source updates with per-machine command receipts."""

from threading import Lock, Thread

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from .. import __version__
from ..automation.api.machine_status.commands import submit_source_update
from ..updates.source import SourceUpdater, source_install
from .machine_status_format import machine_slots


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
        Thread(
            target=self._run, args=(machines, revision, version),
            daemon=True, name="fleet-source-update",
        ).start()
        return True

    def _run(self, machines, revision, version):
        sent, failures = [], []
        try:
            for machine in machines:
                name = str(machine.get("machine_name") or "未知机器")
                try:
                    command = self.submit(
                        machine["machine_id"], revision, version,
                    )
                    sent.append({"machine": name, "command": command})
                except Exception as error:
                    failures.append({"machine": name, "error": str(error)})
        finally:
            self.lock.release()
            self.completed.emit({"sent": sent, "failures": failures})


class FleetUpdatePanel(QGroupBox):
    commands_submitted = Signal()

    def __init__(self, parent=None):
        super().__init__("11 台电脑源码更新", parent)
        self.machines = []
        self.commands = []
        self.submitter = FleetUpdateSubmitter(self)
        self.submitter.completed.connect(self._completed)
        self.summary = QLabel(f"目标版本 {__version__} · 尚未读取机器状态")
        self.summary.setWordWrap(True)
        self.button = QPushButton("一键更新所有已登记电脑")
        self.button.clicked.connect(self.start_all)
        self.table = QTableWidget(11, 3)
        self.table.setHorizontalHeaderLabels(("电脑", "当前版本", "更新状态"))
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumHeight(420)
        header = QHBoxLayout()
        header.addWidget(self.summary, 1)
        header.addWidget(self.button)
        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self.table)
        self.set_data([], [])

    def set_data(self, machines, commands):
        self.machines = list(machines)
        self.commands = list(commands)
        slots = machine_slots(self.machines, 11)
        updated = registered = 0
        for row, machine in enumerate(slots):
            name, version, state = f"M{row + 1}", "—", "未接入"
            if machine is not None:
                registered += 1
                version = str(machine.get("app_version") or "未知")
                state = update_state(machine, self.commands, __version__)
                if version == __version__:
                    updated += 1
            for column, value in enumerate((name, version, state)):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.summary.setText(
            f"目标版本 {__version__} · 已更新 {updated}/11 · 已登记 {registered}/11"
        )
        pending = any(
            machine is not None and not machine.get("identity_conflict")
            and str(machine.get("app_version") or "") != __version__
            for machine in slots
        )
        self.button.setEnabled(pending and source_install() and not self.submitter.lock.locked())

    def has_active_updates(self):
        return any(
            command.get("action") == "source_update"
            and command.get("status") in ACTIVE
            for command in self.commands
        )

    def start_all(self):
        try:
            updater = SourceUpdater()
            updater.validate()
            revision = updater.git_run("rev-parse", "HEAD").strip().lower()
            published = updater.git_run(
                "rev-parse", "refs/remotes/origin/main"
            ).strip().lower()
            if revision != published:
                raise ValueError("当前源码尚未推送到 origin/main，不能下发给其他电脑。")
        except Exception as error:
            self.summary.setText(f"无法发布更新：{error}")
            return
        targets = [
            machine for machine in machine_slots(self.machines, 11)
            if machine is not None and not machine.get("identity_conflict")
            and machine.get("machine_id")
            and str(machine.get("app_version") or "") != __version__
        ]
        missing = 11 - len([item for item in machine_slots(self.machines, 11) if item])
        text = (
            f"向 {len(targets)} 台已登记电脑下发 {__version__} 更新。"
            f"未接入机位 {missing} 台不会收到本次指令。\n\n"
            "正在运行的任务不会被强制停止；源码完成后程序在安全时机重启。"
        )
        if QMessageBox.question(self, "确认更新全部电脑", text) != QMessageBox.Yes:
            return
        if self.submitter.start(targets, revision, __version__):
            self.button.setEnabled(False)
            self.summary.setText(f"正在向 {len(targets)} 台电脑下发更新…")

    def _completed(self, result):
        sent, failures = result["sent"], result["failures"]
        self.summary.setText(
            f"已下发 {len(sent)} 台 · 失败 {len(failures)} 台；正在等待目标机回执。"
            + (" " + "；".join(
                f"{item['machine']}：{item['error']}" for item in failures
            ) if failures else "")
        )
        self.commands_submitted.emit()


def update_state(machine, commands, target_version):
    if machine.get("identity_conflict"):
        return "机器号冲突"
    if str(machine.get("app_version") or "") == str(target_version):
        return "已更新"
    machine_id = str(machine.get("machine_id") or "")
    matches = [
        item for item in commands
        if item.get("action") == "source_update"
        and str(item.get("target_machine_id") or "") == machine_id
    ]
    if not matches:
        return "待更新"
    command = max(matches, key=lambda item: str(item.get("created_at") or ""))
    status = str(command.get("status") or "")
    label = {
        "queued": "等待领取", "claimed": "已领取", "running": "更新中",
        "succeeded": "源码已更新，等待重启回报", "failed": "更新失败",
        "cancelled": "已被新版本替代", "expired": "未领取，已过期",
    }.get(status, status or "状态未知")
    detail = command.get("phase") or command.get("error_message")
    return f"{label} · {detail}" if detail else label
